import appdaemon.plugins.hass.hassapi as hass
import datetime
from pprint import pprint
import ada.schedule 

class HassBase(hass.Hass):

    def my_notify (self,msg):
        t=datetime.datetime.now().strftime("%H:%M:%S")
        n_msg = t +' ' + msg
        self.log(n_msg);
        self.notify(n_msg);

    def is_state_valid (self,state):	
        if state in ['on','off']:	
            return True	
        else:	
            return False	

    def are_states_valid(self,new,old):	
        if self.is_state_valid(new) and self.is_state_valid(old):	
            return True	
        else:	
            return False	

    def read_ent_as_float(self,name,def_val=0.0):	
        res=def_val;	
        try:	
          val=self.get_state(name)	
          if val is not None:	
               res=float(val)	
        except ValueError:	
          pass;	
        return(res)	

    def remove_var_prefix (self,entity):	
        a = entity.split(".")	
        assert(len(a)==2)	
        assert(a[0]=='variable')	
        return (a[1])	

    def var_set (self,entity,val):	
       var = self.remove_var_prefix(entity) 	
       self.call_service('variable/set_variable', variable=var,value=val)	

    def var_inc (self,entity,value):	
       val = self.read_ent_as_float(entity)	
       val += value	
       var = self.remove_var_prefix(entity) 	
       self.call_service('variable/set_variable', variable=var,value="{:.1f}".format(val))	

    def var_dec (self,entity,value):	
       val = self.read_ent_as_float(entity)	
       val -= value	
       var = self.remove_var_prefix(entity) 	
       self.call_service('variable/set_variable', variable=var,value="{:.1f}".format(val))


class CWBIrrigation(HassBase):
    """  """
    #input: 
    #output: 
    def initialize(self):
        self.log("start irrigation app");
        self.h ={}
        self.init_all_taps()
    
    def init_all_taps(self):
        hours = self.args["m_temp_hours"]
        tmean = self.args["m_temp_celsius"]
        self.max_ev_week = 7.0 * hours * (0.46 * tmean + 8.13)
        for tap in self.args["taps"]:
             self.turn_off(tap["switch"])
             self.register_call_backs(tap)
             self.listen_state(self.do_button_change,tap["switch"],tap=tap)
             self.h[tap["name"]] = None

    def do_button_change (self,entity, attribute, old, new, kwargs):
        tap = kwargs['tap']
        h = self.h[tap["name"]] 

        if h is None:
           # manual start 
            if new == "on":
                duration_sec = float(self.get_state(tap["manual_duration"]))*60.0
                self.log("turn on by user {} {} min ".format(tap["name"],int(duration_sec/60.0)))
                self.start_tap(tap, int(duration_sec) , "manual",False)
        else:
            if new == "off":
              # tuen off by user 
              self.log("turn off by user {} ".format(tap["name"]))
              kwargs={}
              kwargs['tap']=tap
              kwargs['clear_queue']=False
              self.time_cb_event_stop(kwargs)
                

    def register_call_backs(self,tap):
        start_time = self.parse_time(tap["stime"])
        start_days = tap["days"]
        days = []
        for day in start_days: 
            days.append(ada.schedule.day_of_week(day))
        days=str(days)[1:-1].replace("'", "").replace(" ","")    
        self.log("irrigation init {} {} {} ".format(tap["name"],days,start_time))
        self.run_daily(self.time_cb_event, 
            start_time, 
            constrain_days = days,
            tap=tap)

        #run next irrigation duration calcs hourly in order to show it in UI 
        checktime = datetime.time(0, 0, 0)
        self.run_hourly(self.calc_next_duration, 
            checktime, 
            tap=tap)

    #set scheduled_duration via service to make it visible in UI
    def set_scheduled_duration(self,tap,val):
       self.call_service('input_number/set_value', entity_id=tap["scheduled_duration"],value=val)

    #calculate next irrigation duration without runninr irrigation, just calculate
    def calc_next_duration(self,kwargs):
        tap = kwargs['tap']
        queue = float(self.get_state(tap["queue_sensor"]))
        duration_min = self.read_ent_as_float(tap["m_week_duration_min"])
        irrigation_time_min = int((-queue) *  duration_min / self.max_ev_week)
        if irrigation_time_min < 0: irrigation_time_min = 0
        # self.log("Next irrigation planned duration: tap {},{} min".format(tap["name"],irrigation_time_min))  # log if you wish to see in in the log
        self.set_scheduled_duration(tap, irrigation_time_min)

    def time_cb_event_stop_verify(self,kwargs):
        tap = kwargs['tap']
        if self.get_state(tap["switch"]) == "on":
           self.turn_off(tap["switch"])
           self.my_notify ("ERROR can't stop tap {}".format(tap["name"]))
           self.run_in(self.time_cb_event_stop_verify, 5,tap=tap)

    def time_cb_event_stop(self,kwargs):
        tap = kwargs['tap']

        state = self.get_state(tap["switch"])
        if state == 'off':
           self.log(" irrigation stop but already off {} ".format(tap["name"]))
        
        self.log(" irrigation stop for {} {}".format(tap["name"],state))
        self.turn_off(tap["switch"])
        
        if self.get_state(tap["switch"]) == "on":
           self.run_in(self.time_cb_event_stop_verify, 5,tap=tap)

        if self.is_water_sensor_defined():
           self.inc_sensor( tap["water_sensor"],
                         self.read_water_sensor () - tap["start"])
                         
        if kwargs['clear_queue']:
           self.reset_queue (tap)
        self.h[tap["name"]] = None    

    def is_water_sensor_defined (self):
       if "water_sensor" in self.args:
          return True
       else:
          return False

                  
    def read_water_sensor (self):
       if self.is_water_sensor_defined():
           return float(self.get_state(self.args["water_sensor"]))
       else:
           return 0.0 # not supported     

    def reset_queue (self,tap):
       self.call_service('wb_irrigation/set_value', entity_id=tap["queue_sensor"],value="0.0")
    
    def inc_sensor (self,sensor,val):
        self.var_inc (sensor,val)

    def start_tap (self,tap,duration_sec,desc,clear_queue):
        duration_min = int(duration_sec/60.0)
        msg = "irrigation time tap {} {} {} min".format(tap["name"],desc,duration_min)
        self.log("irrigation time tap {} {} {} min".format(tap["name"],desc,duration_min)) #logging irrigation time just in case you are courious ;-)
        self.var_inc (tap["time_sensor"],duration_min)
        if "tap_open" in self.args["notify"]:
           self.my_notify(msg)

        h = self.h[tap["name"]]      

        if h:
           self.cancel_timer(h)
           self.h[tap["name"]] = None

        self.h[tap["name"]] = self.run_in(self.time_cb_event_stop, 
                        duration_sec, 
                        tap=tap,clear_queue=clear_queue)

        tap["start"] = self.read_water_sensor ()
        self.turn_on(tap["switch"])
    
    
    def time_cb_event(self,kwargs):
        if self.get_state(self.args["enabled"]) != "on":
            self.log(" irrigation is disabled ")
            return;
           
        tap = kwargs['tap']
        self.log(" irrigation event for {}".format(tap["name"]))
        
        # calculate the irrigation time 
        queue = float(self.get_state(tap["queue_sensor"]))
        if queue > 0.0:
           self.log(" irrigation nothing to do queue: {} ".format(queue))
           return;

        duration_min = self.read_ent_as_float(tap["m_week_duration_min"])
        
        irrigation_time_min =  (-queue) *  duration_min / self.max_ev_week
        if irrigation_time_min < 0.2:
           self.log(" irrigation  queue is small  {} ".format(queue))
           return; 

        if irrigation_time_min > duration_min:
           self.my_notify(" ERROR irrigation time is high {} min ".format(irrigation_time_min))
           self.log(" ERROR irrigation time is high {} min ".format(irrigation_time_min)) #logging error
           irrigation_time_min = duration_min

        self.start_tap(tap, irrigation_time_min * 60, "timer",True)
            

