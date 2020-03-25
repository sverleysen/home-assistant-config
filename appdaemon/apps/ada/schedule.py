"""
This module implements the Schedule and Rule classes.
"""

import typing as T  # pylint: disable=unused-import

import collections
import datetime
import util


def _dtime2sec(day:int,time: datetime.time):
    r = (day-1)*60*60*24 + time.hour*24*60 + time.minute*60+ time.second
    return r


def _dtime2sec_match(iday:int,itime: datetime.time,
                     sday:int, stime: datetime.time,
                     eday:int, etime: datetime.time):
    """ return true if input d:time in in the middle if start:end d/time"""
    i=_dtime2sec(iday,itime)
    s=_dtime2sec(sday,stime)
    e=_dtime2sec(eday,etime)
    if e<s:
       e+=_dtime2sec(8,datetime.time(0, 0))

    if i<=e and i>=s:
        return True
    return False


def day_of_week(day:int):
    """day in format of 1-7 1 is sunday to saturday"""
    nums = ["sun","mon", "tue", "wed", "thu", "fri", "sat" ]
    if type(day) == int:
        return nums[day-1]
    raise ValueError("Incorrect type for 'day' in day_of_week()'")





class Rule:
    """A rule that can be added to a schedule."""

    def __init__(
            self,
            ad,
            start_time: datetime.time = None, 
            start_day : int = 0,
            end_time: datetime.time = None,
            end_day : int = 0,
            mode: str = None
        ) -> None:
        self.ad=ad
        if start_time is None:
            start_time = datetime.time(0, 0)
        self.start_time = ad.parse_time(start_time)
        self.start_day = start_day

        if end_time is None:
            end_time = datetime.time(0, 0)
        self.end_time = ad.parse_time(end_time)
        self.end_day = end_day

        self.mode = "default"
        if mode is not None:
             self.mode = mode

    def __repr__(self) -> str:
        return "<Rule {}>".format(
            ", ".join(["{}={}".format(k, v)
                       for k, v in self._get_repr_properties().items()])
        )

    def _get_repr_properties(self) -> T.Dict[str, T.Any]:
        """Returns an OrderedDict with properties to be shown in repr()."""
        props ={}
        props["start"] = self.start_time
        props["end"]   = self.end_time
        props["mode"]  = self.mode
        props["sday"]  = self.start_day
        props["eday"]  = self.end_day
        return props

    def is_match(self, when: datetime.datetime) -> bool :
         d = when.date().isoweekday()+1
         t = when.time()
         return (_dtime2sec_match(d,t,
                                self.start_day,
                                self.start_time,
                                self.end_day,
                                self.end_time))

    @staticmethod
    def load_cfg(ad,rule: dict):
        """Builds and returns a schedule rule from the given rule
        definition."""
    
        kwargs = {
            "start_time": rule["start"]["t"],
            "start_day": rule["start"]["d"],
            "end_time": rule["end"]["t"],
            "end_day": rule["end"]["d"],
            "mode": rule.get("mode"),
        }
    
        return Rule(ad,**kwargs)


class Schedule:
    """Holds the schedule with all its rules."""

    def __init__(self, ad, cfg: dict,callback=None,cb_data=None):
        self.ad=ad
        self.cfg =cfg
        self.on_cb=callback
        self.cb_data =cb_data
        self.rules = []
        self.__load_yaml();

    def __load_yaml (self):
        for rule in self.cfg:
            self.rules.append(Rule.load_cfg(self.ad,rule))

    def __repr__(self) -> str:
        s="<Schedule with {} rules> \n".format(len(self.rules))
        s+='=================================\n'
        for rule in self.rules:
            s+=rule.__repr__();
            s+="\n";
        return(s);

    def init (self):
        now = self.ad.get_now()
        rule=self.matching_rule(now)
        if rule:
           self._cb_event(dict(rule=rule,state="on"))
        else:
           self._cb_event(dict(rule=None,state="off"))

        for rule in self.rules:
           self.ad.run_daily(self._cb_event, 
                             rule.start_time, 
                             constrain_days=day_of_week(rule.start_day),
                             rule=rule,state="on")
           self.ad.run_daily(self._cb_event, 
                             rule.end_time, 
                             constrain_days=day_of_week(rule.end_day),
                             rule=rule,state="off")

    def matching_rule(self, when: datetime.datetime) -> Rule :
        """Returns the match rule for a time"""
        for rule in self.rules:
            if rule.is_match(when):
                return rule
        return None


    def _cb_event(self,kwargs):
        """ kwargs include 
           rule=rule
           state=on/off 
        """
        kwargs['data']=self.cb_data
        self.on_cb(kwargs)