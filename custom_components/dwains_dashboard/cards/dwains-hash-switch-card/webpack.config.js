const path = require('path');

module.exports = {
  entry: './src/main.js',
  mode: 'production',
  output: {
    filename: 'dwains-hash-switch-card.js',
    path: path.resolve(__dirname)
  }
};
