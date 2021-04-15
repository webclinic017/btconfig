"""
Backtrader setup running lib with support for config files

The backtrader system will be configured and set up by using config files.
The possible configuration options are described below.

Intention
---------

    The intention of btconfig is to provide a basic framework for automatic
    strategy setup using a config file. This allows to collect different
    strategies, indicators, etc. and to setup and execute a strategy in
    different execution modes:

    * LIVE
    * BACKTEST
    * OPTIMIZE

    Every execution mode can set different settings for data sources, parts to
    use and so on.

How to run
----------

    To run a strategy you first need to create a config file.

    If a config file is available:
    btconfig.run(mode, configfile)

    where mode is either LIVE, BACKTEST or OPTIMIZE and configfile
    is the filename of the config file.

    Additional seearch paths and settings can be changed before executing.

    Simple example:
    ```
    import btconfig

    if __name__ == '__main__':
        btconfig.run(btconfig.MODE_BACKTEST, "config.json")
    ```

    Example with customization:

    ```
    import btconfig
    from btconfig import BTConfig

    btconf = BTConfig()
    btconf.PATH_STRATEGY.append('other_stratgies')

    if __name__ == '__main__':
        btconf.run(btconfig.MODE_BACKTEST, "config.json")
    ```

Config file
-----------

    #### [common]
    Common configuration

        * time (datetime): The time btconfig was initialized
        * strategy (string): The name of the strategy to use
        * timezone (string): The timezone of data
        * create_plot (bool): Should the plot be created
        * create_report (bool): Should a report be created
        * broker (string): The broker to use
        * cash (float): The start amount of cash

    #### [logging]
    Configuration for logging

        * enabled (bool): Should logging be enabled (true/false)
        * console (bool): Should log entries be logged to console (true/false)
        * file (bool): Should log entries be logged into files (true/false)
        * level (string): Log level to log (ex. "INFO")
        * file_path (string): Path for file logs (ex. "./logs")

    See btconfig.parts.logging for more details

    #### [cerebro]
    Configuration for cerebro

    Supports all backtrader params. Based on the mode different
    defaults will be preset. name/value pairs.

    See btconfig.parts.cerebro for more details

    #### [stores]
    Configuration for stores

        Allows to setup different stores which
        are differentiated by the store_name.

        * store_name (string: dict): Configuration for a single store

        The following stores are supported:

        * oandav20: Oanda V20
        * ib: Interactive Brokers

        Every store can individually be configured by providing
        different params in the dict.

    See btconfig.parts.store for more details

    #### [feeds]
    Configuration for data feeds of strategy

        * feed_name (string: list): Configuration for a single feed
        Where list expects the values:
        [Timeframe, Compression, Method, Options]

    See btconfig.parts.data for more details

    #### [datas]
    Configuration for data sources

        * identifier (string: dict)
        Where dict contains data config values

    See btconfig.parts.data for more details

    #### [sizer]
    Configuration for sizer

        * classname (str): Classname to use
        * params (dict): name/value pairs for class params

    See btconfig.parts.sizer for more details

    #### [comminfo]
    Configuration for comminfo

        * classname (str): Classname to use
        * params (dict): name/value pairs for class params

    See btconfig.parts.comminfo for more details

    #### [plot]
    Configuration for plotting

        * use (string): use=web for web interface, TKAgg etc.
        * path (string): Path for backtest output
        * plot_volume (bool): Should volume be added to plotting (true/false)
        * bar_dist (float): Distance of markers to bars (ex. 0.0003)
        * style (string): Plot style for bars (ex. "candle")
        * combine (bool): Should different feeds be combined to a
        single plot (true/false)
        * web_port (int): Web port for btplotting (ex. 80)
        * live_lookback (int): Lockback of bars for live plotting (ex. 50)

    See btconfig.parts.plot for more details

    #### [analyzers]
    Configuration for analyzers
    **Only temporary**

        * time_return (list): ["Minutes", 240]
        * sharpe_ratio (list): ["Days", 1, 365, true]
        Timeframe, Compression, Factor, Annualize
        Config based on:
        https://community.backtrader.com/topic/2747/how-to-initialize-bt-analyzers-sharperatio/13

    See btconfig.parts.backtrader for more details

    #### [strategy]
    Configuration for strategy
    Contains dict with config for different classes

        ProtoStrategy:
        Configuration for prototype strategy
            * valuename (string/number):
              Set common strategy param to given value

        ForexProtoStrategy:
        Configuration for forex prototype strategy
            * valuename (string/number):
              Set common strategy param to given value

        StrategyName:
        Configuration for strategy with given name
            * valuename (string/number): Set strategy param to given value

    #### [_live]
    Configuration when using live trading

        * cerebro (dict): Cerebro params

    #### [_backtest]
    Configuration when using backtesting / optimization

        * cerebro (dict): Cerebro params

    #### [_optimize]
    Configuration when using optimization

    Optimization is using the configuration for backtest
    with additional possibilities to set custom config values.

        * cerebro (dict): Cerebro params
        * values (dict): Values to use for optimization
            * valuename: ["list", ["value 1", "value 2"]]:
            List of values to use: list with values
            * valuename: ["range", 8, 10, 1]:
            Range of numerical values to use: start, end, step
"""

from __future__ import division, absolute_import, print_function

import backtrader as bt

import json
import logging

from datetime import datetime

from .helper import get_classes, merge_dicts


# dev info
__author__ = "Daniel Schindler <daniel@vcard24.de>"
__status__ = "development"

# constants
TIMEFORMAT = '%Y-%m-%dT%H:%M:%S'
NUMBERFORMAT = '0,0.000[000]'
MODE_LIVE, MODE_BACKTEST, MODE_OPTIMIZE = range(3)
MODES = ['LIVE', 'BACKTEST', 'OPTIMIZE']

# default config dicts
CONFIG_DEFAULT = {
    'common': {}, 'cerebro': {}, 'stores': {}, 'broker': {},
    'datas': {}, 'feeds': {}, 'sizer': {}, 'comminfo': {},
    'plot': {}, 'logging': {}, 'analyzers': {}, 'strategy': {},
    '_live': {}, '_backtest': {}, '_optimize': {}}
CONFIG_LIVE = {**CONFIG_DEFAULT, **{
    'cerebro': {'stdstats': False, 'live': True}}}
CONFIG_BACKTEST = {**CONFIG_DEFAULT, **{
    'cerebro': {'stdstats': False,
                'live': False,
                'optreturn': False,
                'tradehistory': True}}}
CONFIG_OPTIMIZE = {**CONFIG_DEFAULT, **CONFIG_BACKTEST}


class BTConfig:

    # default search paths for classes
    PATH_BTCONF_PART = ['btconfig.parts']
    PATH_BTCONF_STORE = ['btconfig.stores']
    PATH_BTCONF_FEED = ['btconfig.feeds']
    PATH_COMMINFO = ['commissions',
                     'backtrader.commissions',
                     'btoandav20.commissions']
    PATH_SIZER = ['sizers', 'backtrader.sizers', 'btoandav20.sizers']
    PATH_ANALYZER = ['analyzers', 'backtrader.analyzers', 'btconfig.analyzers']
    PATH_OBSERVER = ['observers', 'backtrader.observers', 'btconfig.observers']
    PATH_STRATEGY = ['strategies']

    def __init__(self, mode: int = None, configfile: str = None) -> None:
        '''
        Initialization
        '''
        # misc vars
        self._logger = logging.getLogger('btconfig')
        self._filename = configfile   # filename of config
        self._config = None           # complete configuration
        self._parts = {}              # all loaded parts
        self._stores = {}             # all loaded stores
        self._feeds = {}              # all loaded feeds
        # global vars
        self.cerebro = None    # cerebro instance
        self.mode = mode       # current mode
        self.config = None     # current configuration
        self.stores = {}       # current stores available
        self.datas = {}        # current data sources
        self.result = []       # store execution result
        # load different parts of btconfig
        self._loadParts()
        self._loadStores()
        self._loadFeeds()

    def _loadParts(self) -> None:
        '''
        Loads all available parts
        '''
        for classname, classobj in get_classes(self.PATH_BTCONF_PART).items():
            self._parts[classname] = classobj(self)

    def _getParts(self) -> list:
        '''
        Returns a sorted list of all available parts
        '''
        return sorted(
            self._parts,
            key=lambda x: self._parts[x].PRIORITY,
            reverse=True)

    def _loadStores(self) -> None:
        '''
        Loads all available stores
        '''
        for classname, classobj in get_classes(self.PATH_BTCONF_STORE).items():
            self._stores[classname] = classobj(self)

    def _getStores(self) -> list:
        '''
        Returns a sorted list of all available stores
        '''
        return [self._stores[x] for x in self._stores]

    def _loadFeeds(self) -> None:
        '''
        Loads all available feeds
        '''
        for classname, classobj in get_classes(self.PATH_BTCONF_FEED).items():
            self._feeds[classname] = classobj(self)

    def _getFeeds(self) -> list:
        '''
        Returns a sorted list of all available feeds
        '''
        return [self._feeds[x] for x in self._feeds]

    def _getConfigForMode(self, mode: int) -> dict:
        '''
        Returns the config for the given mode

            Args:
            -----
            - mode (int): The mode the config will be generated for

            Returns:
            --------
            dict
        '''
        # use default config based on mode and merge with config
        if mode == MODE_LIVE:
            res = CONFIG_LIVE
            merge_dicts(res, self._config.get('_live', {}))
        elif mode == MODE_BACKTEST:
            res = CONFIG_BACKTEST
            merge_dicts(res, self._config.get('_backtest', {}))
        elif mode == MODE_OPTIMIZE:
            res = CONFIG_OPTIMIZE
            merge_dicts(res, self._config.get('_backtest', {}))
            merge_dicts(res, self._config.get('_optimize', {}))
        else:
            raise Exception('Unknown mode provided')
        merge_dicts(res, self._config)
        # remove override sections
        for v in ['_live', '_backtest', '_optimize']:
            if v in res:
                del(res[v])
        # return config for given mode
        return res

    def _prepare(self, mode: int, configfile: str) -> None:
        '''
        Initialization of btconfig using a config file

        Args:
        -----
        - mode (int): Optional, the mode to execute
        - configfile (str): Optional, configfile to use

        Returns:
        --------
        None
        '''
        # load config from filename
        if configfile is not None:
            self._filename = configfile
        if self._filename is None:
            raise Exception('No config file defined')
        with open(self.filename, 'r') as file:
            self._config = json.load(file)
        merge_dicts(self._config, CONFIG_DEFAULT)
        # store time at which btconfig was initialized
        self._config['common']['time'] = datetime.now()

        # set mode
        if mode is not None:
            self.mode = mode
        if self.mode is None:
            raise Exception('No run mode defined')
        # set config for mode
        self.config = self._getConfigForMode(mode)

        # set empty dicts
        self.stores = {}
        self.datas = {}

        # reset result
        self.result = []

    def _setup(self) -> None:
        '''
        Sets all parts of backtrader

            Returns:
            --------
            None
        '''
        for p in self._parts:
            p.setup()

    def _finish(self) -> None:
        '''
        Finishes execution of backtrader

            Returns:
            --------
            None
        '''
        self.result = self.cerebro.run()
        for p in self._parts:
            p.finish(self.result)

    def run(self, mode: int = None, configfile: str = None) -> list:
        self._prepare(mode, configfile)
        self._setup()
        self._finish()
        return self._result

    def log(self, txt: str, level: int = logging.INFO) -> None:
        '''
        Logs text

            Args:
            -----
            - txt (str): The text to log
            - level (int): The log level

            Returns:
            --------
            None
        '''
        if self.config is None:
            raise Exception('No config loaded')
        if self.config['logging'].get('enabled', True):
            self._logger.log(level, txt)
        else:
            print(txt)


class BTConfigItem:

    def __init__(self, instance: BTConfig) -> None:
        self._instance = instance

    def log(self, txt: str, level: int = logging.INFO) -> None:
        self._instance.log(txt, level)


class BTConfigPart(BTConfigItem):

    PRIORITY = 0

    def setup(self) -> None:
        pass

    def finish(self) -> None:
        pass


class BTConfigStore(BTConfigItem):

    def create(self, cfg: dict) -> bt.Store:
        raise Exception('Method create needs to be overwritten')


class BTConfigFeed(BTConfigItem):

    def create(self, cfg, tz) -> bt.AbstractDataBase:
        raise Exception('Method create needs to be overwritten')


def run(mode: int = None, configfile: str = None) -> BTConfig:
    '''
    Runs the strategy

    Main method to setup backtrader and run a strategy
    using configuration from a configfile.

        Args:
        -----
        - mode (int): Optional, the mode to run
        - configfile (str): Optional, configfile to use

        Returns:
        --------
        BTConfig
    '''
    config = BTConfig()
    config.run(mode, configfile)
    return config


def run_live(configfile: str = None) -> BTConfig:
    '''
    Shortcut method to execute live mode

        Args:
        -----
        - configfile (str): Config filename to use

        Returns:
        --------
        BTConfig
    '''
    return run(MODE_LIVE, configfile)


def run_backtest(configfile: str = None) -> BTConfig:
    '''
    Shortcut method to execute backtest mode

        Args:
        -----
        - configfile (str): Config filename to use

        Returns:
        --------
        BTConfig
    '''
    return run(MODE_BACKTEST, configfile)


def run_optimize(configfile: str = None) -> BTConfig:
    '''
    Shortcut method to execute optimization mode

        Args:
        -----
        - configfile (str): Config filename to use

        Returns:
        --------
        BTConfig
    '''
    return run(MODE_OPTIMIZE, configfile)
