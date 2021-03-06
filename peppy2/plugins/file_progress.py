# Standard library imports.
import os
import time
import wx
import wx.lib.newevent

# Enthought library imports.
from traits.api import HasTraits, on_trait_change, Any, Instance, List, Bool, Int, Range, Str, Unicode, Event
from envisage.api import ExtensionPoint, Plugin

# Local imports.
from peppy2.framework.plugin import FrameworkPlugin
from peppy2.framework.errors import ProgressCancelError

import logging
log = logging.getLogger(__name__)

# wx logging handler from http://stackoverflow.com/questions/2819791/how-can-i-redirect-the-logger-to-a-wxpython-textctrl-using-a-custom-logging-hand
# create event type
wxLogEvent, EVT_WX_LOG_EVENT = wx.lib.newevent.NewEvent()


class ProgressDialog(wx.Dialog):
    def __init__(self, parent, title="Progress", delay=1000):
        wx.Dialog.__init__(self, parent, -1, title,
                           size=wx.DefaultSize, pos=wx.DefaultPosition, 
                           style=wx.DEFAULT_DIALOG_STYLE)
        self.border = 20
        self.delay = delay
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.label = wx.StaticText(self, -1, "Working...")
        self.label.SetMinSize((400, -1))
        sizer.Add(self.label, 0, flag=wx.EXPAND|wx.ALL, border=self.border)

        self.progressHeight = 12
        self.gauge = wx.Gauge(self, -1,
              range=100, size = (-1, self.progressHeight),
              style=wx.GA_HORIZONTAL|wx.GA_SMOOTH)
        sizer.Add(self.gauge, 0, flag=wx.EXPAND|wx.ALL, border=self.border)

        self.count = 0
        self.last_pulse = time.clock()
        self.time_delta = 0.1

        self.visible = False
        self._delaytimer = wx.PyTimer(self.on_timer)
        self.is_pulse = True

        btnsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(self, wx.ID_CANCEL)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        btnsizer.Realize()
        sizer.Add(btnsizer, 0, flag=wx.EXPAND|wx.ALL, border=5)
        btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.request_cancel = False

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.label.Layout()
        self.gauge.Layout()
        self.Layout()
        self.CenterOnParent()

    def on_cancel(self, evt):
        self.request_cancel = True
    
    def raise_error(self):
        raise ProgressCancelError(self.GetTitle() + " canceled by user!")

    def start_visibility_timer(self):
        if not self._delaytimer.IsRunning():
            self._delaytimer.Start(self.delay, oneShot=True)

    def stop_visibility_timer(self):
        if self._delaytimer.IsRunning():
            self._delaytimer.Stop()

    def on_timer(self):
        self.Show()

    def set_ticks(self, count):
        """Set the total number of ticks that will be contained in the
        progress bar.
        """
        self.gauge.SetRange(count)
        self.count = 0
        self.last_pulse = 0 # force update next time
        self.is_pulse = False

    def is_update_time(self):
        t = time.clock()
        if t - self.last_pulse > self.time_delta:
            self.last_pulse = t
            return True
        return False

    def set_pulse(self):
        """Set the total number of ticks that will be contained in the
        progress bar.
        """
        if self.is_update_time():
            self.gauge.Pulse()
        self.is_pulse = True
        wx.Yield()

    def tick(self, text=None, index=None):
        """Advance the progress bar by one tick and update the label.
        """
        ok = self.is_update_time()
        if self.is_pulse:
            if text:
                self.label.SetLabel(text)
            if ok:
                self.gauge.Pulse()
        else:
            if text:
                self.label.SetLabel(text)
            if index is None:
                self.count += 1
            else:
                self.count = index
            if self.count > self.gauge.GetRange():
                self.set_pulse()
            elif ok:
                self.gauge.SetValue(self.count)
        self.gauge.Update()
        wx.Yield()


class wxLogHandler(logging.Handler):
    """
    A handler class which sends log strings to a wx object
    """
    
    progress_dialog = None
    
    disabler = None
    
    def __init__(self, default_title=""):
        """
        Initialize the handler
        @param wxDest: the destination object to post the event to 
        @type wxDest: wx.Window
        """
        logging.Handler.__init__(self)
        self.level = logging.DEBUG
        self.default_title = default_title

    def flush(self):
        """
        does nothing for this handler
        """

    def emit(self, record):
        """
        Emit a record.

        """
        msg = self.format(record)

        # Handle progress cancel request here, the only place that's not inside
        # a wx event handler.  Attempting to handle inside an event handler
        # doesn't propagate outside the event handler.
        d = self.__class__.progress_dialog
        if d and d.request_cancel and msg != "END":
            # change flag so multiple requests are not processed
            d.request_cancel = False
            raise ProgressCancelError(d.GetTitle() + " canceled by user!")

        try:
            evt = wxLogEvent(message=msg,levelname=record.levelname)
            self.post(evt)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
    
    @classmethod
    def get_dialog(cls):
        if cls.progress_dialog is None or not cls.progress_dialog:
            top = wx.GetApp().GetTopWindow()
            cls.progress_dialog = ProgressDialog(top)
        return cls.progress_dialog
    
    @classmethod
    def get_dialog_if_open(cls):
        if cls.progress_dialog is None or not cls.progress_dialog:
            return None
        return cls.progress_dialog
    
    @classmethod
    def open_dialog(cls):
        d = cls.get_dialog()
        # Forcibly disable all windows (other than the progress dialog) to
        # prevent user event processing in the wx.Yield calls.
        cls.disabler = wx.WindowDisabler(d)
        wx.BeginBusyCursor()
        return d
    
    @classmethod
    def close_dialog(cls):
        d = cls.get_dialog_if_open()
        if d is not None:
            cls.disabler = None
            d.stop_visibility_timer()
            d.Destroy()
            wx.Yield()
            wx.EndBusyCursor()  # fails in wx 3.0 before Yield
        cls.progress_dialog = None
    
    def force_cursor(self):
        # OS X resets the busy cursor when the cursor moves out of the dialog,
        # so at every tick call this method to reset it to the wait cursor.
        # Other platforms don't have this problem.
        wx.SetCursor(wx.StockCursor(wx.CURSOR_WAIT))
    
    def post(self, evt):
        m = evt.message
        if m.startswith("START"):
            d = self.open_dialog()
            if "=" in m:
                _, text = m.split("=", 1)
                d.SetTitle(text)
            else:
                d.SetTitle(self.default_title)
            d.start_visibility_timer()
            wx.Yield()
        elif m == "END":
            self.close_dialog()
        else:
            d = self.get_dialog_if_open()
            if d is None:
                # skipping log message to dialog if no dialog is open
                return
            if m.startswith("TITLE"):
                self.force_cursor()
                _, text = m.split("=", 1)
                d.SetTitle(text)
                wx.Yield()
            elif m.startswith("TICKS"):
                self.force_cursor()
                _, count = m.split("=", 1)
                d.set_ticks(int(count))
            elif m.startswith("TICK"):
                self.force_cursor()
                if "=" in m:
                    _, count = m.split("=", 1)
                    d.tick(index=int(count))
                else:
                    d.tick()
            elif m == "PULSE":
                self.force_cursor()
                d.set_pulse()
            else:
                self.force_cursor()
                d.tick(m)


class FileProgressPlugin(FrameworkPlugin):
    """wx dialog to monitor file load/save through the logging framework
    
    """

    wx_dialog = None

    #### 'IPlugin' interface ##################################################

    # The plugin's unique identifier.
    id = 'file_progress'

    # The plugin's name (suitable for displaying to the user).
    name = 'Recently Opened Files List'

    def start(self):
        log = logging.getLogger("progress")
        log.propagate = False
        handler = wxLogHandler("Progress")
        log.addHandler(handler)
