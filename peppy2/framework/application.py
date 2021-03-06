import os
import sys
import argparse
from datetime import datetime

import logging
log = logging.getLogger(__name__)

# Create the wx app here so we can capture the Mac specific stuff that
# traitsui.wx.toolkit's wx creation routines don't handle.  Also, monkey
# patching wx.GetApp() to add MacOpenFile (etc) doesn't seem to work, so we
# have to have these routines at app creation time.
import wx
class EnthoughtWxApp(wx.App):
    def MacOpenFile(self, filename):
        """OSX specific routine to handle files that are dropped on the icon
        
        """
        if hasattr(self, 'tasks_application'):
            # The tasks_application attribute is added to this wx.App instance
            # when the application has been initialized.  This is used as a
            # flag to indicate that the subsequent calls to MacOpenFile are
            # real drops of files onto the dock icon.  Prior to that, this
            # method gets called for all the command line arguments which would
            # give us two copies of each file specified on the command line.
            log.debug("MacOpenFile: loading %s" % filename)
            self.tasks_application.load_file(filename, None)
        else:
            log.debug("MacOpenFile: skipping %s because it's a command line argument" % filename)

from traits.etsconfig.api import ETSConfig

_app = EnthoughtWxApp(redirect=False)

# Enthought library imports.
from envisage.ui.tasks.api import TasksApplication
from envisage.ui.tasks.task_window_event import TaskWindowEvent, VetoableTaskWindowEvent
from pyface.api import ImageResource
from pyface.tasks.api import Task, TaskWindowLayout
from traits.api import provides, Bool, Instance, List, Property, Str, Unicode, Event, Dict

# Local imports.
from peppy2.framework.preferences import FrameworkPreferences, \
    FrameworkPreferencesPane


def _task_window_wx_on_mousewheel(self, event):
    if self.active_task and hasattr(self.active_task, '_wx_on_mousewheel_from_window'):
        log.debug("calling mousewheel in task %s" % self.active_task)
        self.active_task._wx_on_mousewheel_from_window(event)

class FrameworkApplication(TasksApplication):
    """ The sample framework Tasks application.
    """

    #### 'IApplication' interface #############################################

    # The application's globally unique identifier.
    id = 'peppy2.framework.application'

    # The application's user-visible name.
    name = 'Peppy2'

    #### 'TasksApplication' interface #########################################

    # The default window-level layout for the application.
    default_layout = List(TaskWindowLayout)

    # Whether to restore the previous application-level layout when the
    # applicaton is started.
    always_use_default_layout = Property(Bool)

    #### 'FrameworkApplication' interface ####################################

    preferences_helper = Instance(FrameworkPreferences)
    
    startup_task = Str('peppy.framework.text_edit_task')
    
    successfully_loaded_event = Event
    
    plugin_event = Event
    
    preferences_changed_event = Event
    
    plugin_data = {}
    
    command_line_args = List
    
    log_dir = Str
    
    log_file_ext = Str

    ###########################################################################
    # Private interface.
    ###########################################################################

    #### Trait initializers ###################################################
    
    def _about_title_default(self):
        return self.name
    
    def _about_version_default(self):
        from peppy2 import __version__
        return __version__

    def _default_layout_default(self):
        active_task = self.preferences_helper.default_task
        log.debug("active task: -->%s<--" % active_task)
        if not active_task:
            active_task = self.startup_task
        log.debug("active task: -->%s<--" % active_task)
        log.debug("factories: %s" % " ".join([ factory.id for factory in self.task_factories]))
        tasks = [ factory.id for factory in self.task_factories if active_task and active_task == factory.id ]
        log.debug("Default layout: %s" % str(tasks))
        return [ TaskWindowLayout(*tasks,
                                  active_task = active_task,
                                  size = (800, 600)) ]

    def _preferences_helper_default(self):
        return FrameworkPreferences(preferences = self.preferences)

    #### Trait property getter/setters ########################################

    def _get_always_use_default_layout(self):
        return self.preferences_helper.always_use_default_layout


    #### Trait event handlers
    
    def _application_initialized_fired(self):
        log.debug("STARTING!!!")
        for arg in self.command_line_args:
            if arg.startswith("-"):
                log.debug("skipping flag %s" % arg)
            log.debug("processing %s" % arg)
            self.load_file(arg, None)
        app = wx.GetApp()
        app.tasks_application = self
    
    def _window_created_fired(self, event):
        """The toolkit window doesn't exist yet.
        """
    
    def _window_opened_fired(self, event):
        """The toolkit window does exist here.
        """
        log.debug("WINDOW OPENED!!! %s" % event.window.control)
        
        # Check to see that there's at least one task.  If a bad application
        # memento (~/.config/Peppy2/tasks/wx/application_memento), the window
        # may be blank in which case we need to add the default task.
        if not event.window.tasks:
            self.create_task_in_window(self.startup_task, event.window)
            log.debug("EMPTY WINDOW OPENED!!! Created task.")
        
        task = event.window.active_task
        if task.active_editor is None and task.start_new_editor_in_new_window:
            task.new()
        
        if sys.platform.startswith("win"):
            # monkey patch to include mousewheel handler on the TaskWindow
            import types
            event.window._wx_on_mousewheel = types.MethodType(_task_window_wx_on_mousewheel, event.window)
            event.window.control.Bind(wx.EVT_MOUSEWHEEL, event.window._wx_on_mousewheel)

    #### API

    def load_file(self, uri, active_task=None, task_id="", **kwargs):
        service = self.get_service("peppy2.file_type.i_file_recognizer.IFileRecognizerDriver")
        log.debug("SERVICE!!! %s" % service)
        
        from peppy2.utils.file_guess import FileGuess
        # The FileGuess loads the first part of the file and tries to identify it.
        try:
            guess = FileGuess(uri)
        except IOError, e:
            active_task.window.error(str(e), "File Load Error")
            return
        
        # Attempt to classify the guess using the file recognizer service
        service.recognize(guess)
        
        # Short circuit: if the file can be edited by the active task, use that!
        if active_task is not None and active_task.can_edit(guess.metadata.mime):
            active_task.new(guess, **kwargs)
            return
        
        possibilities = []
        for factory in self.task_factories:
            log.debug("factory: %s" % factory.name)
            if task_id:
                if factory.id == task_id:
                    possibilities.append(factory)
            elif hasattr(factory.factory, "can_edit"):
                if factory.factory.can_edit(guess.metadata.mime):
                    log.debug("  can edit: %s" % guess.metadata.mime)
                    possibilities.append(factory)
        log.debug(possibilities)
        if not possibilities:
            log.debug("no editor for %s" % uri)
            return
        
        best = possibilities[0]
        
        if active_task is not None:
            # Ask the active task if it's OK to load a different editor
            if not active_task.allow_different_task(guess, best.factory):
                return

        # Look for existing task in current windows
        task = self.find_active_task_of_type(best.id)
        if task:
            task.new(guess, **kwargs)
            return
        
        # Not found in existing windows, so open new window with task
        tasks = [ factory.id for factory in possibilities ]
        log.debug("no task window found: creating new layout for %s" % str(tasks))
#        window = self.create_window(TaskWindowLayout(size = (800, 600)))
        window = self.create_window()
        log.debug("  window=%s" % str(window))
        first = None
        for factory in possibilities:
            task = self.create_task(factory.id)
            window.add_task(task)
            first = first or task
        window.activate_task(first)
        window.open()
        log.debug("All windows: %s" % self.windows)
        task.new(guess, **kwargs)
        metadata = guess.get_metadata()
        log.debug(guess.metadata)
        log.debug(guess.metadata.mime)
        log.debug(metadata)
        log.debug(metadata.mime)
        log.debug(dir(metadata))
    
    def create_task_in_window(self, task_id, window):
        log.debug("creating %s task" % task_id)
        task = self.create_task(task_id)
        window.add_task(task)
        window.activate_task(task)
        return task
    
    def find_active_task_of_type(self, task_id):
        # Check active window first, then other windows
        w = list(self.windows)
        try:
            i = w.index(self.active_window)
            w.pop(i)
            w[0:0] = [self.active_window]
        except ValueError:
            pass
        for window in w:
            log.debug("window: %s" % window)
            log.debug("  active task: %s" % window.active_task)
            if window.active_task.id == task_id:
                log.debug("  found active task")
                return window.active_task
        log.debug("  no active task matches %s" % task_id)
        for window in w:
            task = window.active_task
            if task is None:
                continue
            # if no editors in the task, replace the task with the new task
            log.debug("  window %s: %d" % (window, len(task.editor_area.editors)))
            if len(task.editor_area.editors) == 0:
                log.debug("  replacing unused task!")
                # The bugs in remove_task seem to have been fixed so that the
                # subsequent adding of a new task does seem to work now.  But
                # I'm leaving in the workaround for now of simply closing the
                # active window, forcing the new task to open in a new window.
                if True:
                    window.remove_task(task)
                    task = self.create_task_in_window(task_id, window)
                    return task
                else:
                    window.close()
                    return None
    
    def find_or_create_task_of_type(self, task_id):
        task = self.find_active_task_of_type(task_id)
        if not task:
            log.debug("task %s not found in active windows; creating new window" % task_id)
            window = self.create_window()
            task = self.create_task_in_window(task_id, window)
            window.open()
        return task

    # Override the default window closing event handlers only on Mac because
    # Mac allows the application to remain open while no windows are open
    if sys.platform == "darwin":
        def _on_window_closing(self, window, trait_name, event):
            # Event notification.
            self.window_closing = window_event = VetoableTaskWindowEvent(
                window=window)

            if window_event.veto:
                event.veto = True
            else:
                # Store the layout of the window.
                window_layout = window.get_window_layout()
                self._state.push_window_layout(window_layout)

        def _on_window_closed(self, window, trait_name, event):
            self.windows.remove(window)

            # Event notification.
            self.window_closed = TaskWindowEvent(window=window)

            # Was this the last window?
            if len(self.windows) == 0 and self._explicit_exit:
                self.stop()

    def _initialize_application_home(self):
        """Override the envisage.application method to force the use of standard
        config directory location instead of ~/.enthought 
        """

        from peppy2.third_party.appdirs import user_config_dir, user_log_dir
        dirname = user_config_dir(self.name)
        ETSConfig.application_home = dirname

        # Make sure it exists!
        if not os.path.exists(ETSConfig.application_home):
            os.makedirs(ETSConfig.application_home)

        dirname = user_log_dir(self.name)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        self.log_dir = dirname
        
        self.log_file_ext = "-%s" % datetime.now().strftime("%Y%m%d-%H%M%S")
        
        return
    
    #### Convenience methods
    
    def get_plugin_data(self, plugin_id):
        return self.plugin_data[plugin_id]
    
    def get_preferences(self, helper_object, debug=True):
        """Get preferences for a particular PreferenceHelper object.
        
        Handle mistakes in preference files by using the default value for any
        bad preference values.
        """
        try:
            helper = helper_object(preferences=self.preferences)
        except TraitError:
            # Create an empty preference object and helper so we can try
            # preferences one-by-one to see which are bad
            empty = Preferences()
            helper = helper_object(preferences=empty)
            if debug:
                log.debug("Application preferences before determining error:")
                self.preferences.dump()
            for t in helper.trait_names():
                if helper._is_preference_trait(t):
                    pref_name = "%s.%s" % (helper.preferences_path, t)
                    text_value = self.preferences.get(pref_name)
                    if text_value is None:
                        # None means the preference isn't specified, which
                        # isn't an error.
                        continue
                    try:
                        empty.set(pref_name, self.preferences.get(pref_name))
                    except:
                        log.error("Invalid preference for %s: %s. Using default value %s" % (pref_name, self.preferences.get(pref_name), getattr(helper, t)))
                        self.preferences.remove(pref_name)
                        # Also remove from default scope
                        self.preferences.remove("default/%s" % pref_name)
            if debug:
                log.debug("Application preferences after removing bad preferences:")
                self.preferences.dump()
            helper = helper_object(preferences=self.preferences)
        return helper
    
    def get_log_file_name(self, log_file_name_base, ext=""):
        filename = log_file_name_base + self.log_file_ext
        if ext:
            if not ext.startswith("."):
                filename += "."
            filename += ext
        else:
            filename += ".log"
        filename = os.path.join(self.log_dir, filename)
        return filename
    
    def save_log(self, text, log_file_name_base, ext=""):
        filename = self.get_log_file_name(log_file_name_base, ext)
        
        try:
            with open(filename, "wb") as fh:
                fh.write(text)
        except IOError:
            log.error("Failed writing %s to %s" % (log_file_name_base, filename))


def run(plugins=[], use_eggs=True, egg_path=[], image_path=[], startup_task="", application_name="", debug_log=False):
    """Start the application
    
    :param plugins: list of user plugins
    :param use_eggs Boolean: search for setuptools plugins and plugins in local eggs?
    :param egg_path: list of user-specified paths to search for more plugins
    :param startup_task string: task factory identifier for task shown in initial window
    :param application_name string: change application name instead of default Peppy2
    """
    # Enthought library imports.
    from envisage.api import PluginManager
    from envisage.core_plugin import CorePlugin
    
    # Local imports.
    from peppy2.framework.plugin import PeppyTasksPlugin, PeppyMainPlugin
    from peppy2.file_type.plugin import FileTypePlugin
    from peppy2 import get_image_path
    from peppy2.utils.jobs import get_global_job_manager
    
    # Include standard plugins
    core_plugins = [ CorePlugin(), PeppyTasksPlugin(), PeppyMainPlugin(), FileTypePlugin() ]
    if sys.platform == "darwin":
        from peppy2.framework.osx_plugin import OSXMenuBarPlugin
        core_plugins.append(OSXMenuBarPlugin())
    
    import peppy2.file_type.recognizers
    core_plugins.extend(peppy2.file_type.recognizers.plugins)
    
    import peppy2.plugins
    core_plugins.extend(peppy2.plugins.plugins)
    
    # Add the user's plugins
    core_plugins.extend(plugins)
    
    # Check basic command line args
    default_parser = argparse.ArgumentParser(description="Default Parser")
    default_parser.add_argument("--no-eggs", dest="use_eggs", action="store_false", default=True, help="Do not load plugins from python eggs")
    options, extra_args = default_parser.parse_known_args()
    print("after default_parser: extra_args: %s" % extra_args)

    # The default is to use the specified plugins as well as any found
    # through setuptools and any local eggs (if an egg_path is specified).
    # Egg/setuptool plugin searching is turned off by the use_eggs parameter.
    default = PluginManager(
        plugins = core_plugins,
    )
    if use_eggs and options.use_eggs:
        from pkg_resources import Environment, working_set
        from envisage.api import EggPluginManager
        from envisage.composite_plugin_manager import CompositePluginManager
        
        # Find all additional eggs and add them to the working set
        environment = Environment(egg_path)
        distributions, errors = working_set.find_plugins(environment)
        if len(errors) > 0:
            raise SystemError('cannot add eggs %s' % errors)
        logger = logging.getLogger()
        logger.debug('added eggs %s' % distributions)
        map(working_set.add, distributions)

        # The plugin manager specifies which eggs to include and ignores all others
        egg = EggPluginManager(
            include = [
                'peppy2.tasks',
            ]
        )
        
        plugin_manager = CompositePluginManager(
            plugin_managers=[default, egg]
        )
    else:
        plugin_manager = default

    # Add peppy2 icons after all image paths to allow user icon themes to take
    # precidence
    from pyface.resource_manager import resource_manager
    import os
    image_paths = image_path[:]
    image_paths.append(get_image_path("icons"))
    resource_manager.extra_paths.extend(image_paths)

    kwargs = {}
    if startup_task:
        kwargs['startup_task'] = startup_task
    if application_name:
        kwargs['name'] = application_name
    app = FrameworkApplication(plugin_manager=plugin_manager, command_line_args=extra_args, **kwargs)
    
    # Create a debugging log
    if debug_log:
        filename = app.get_log_file_name("debug")
        handler = logging.FileHandler(filename)
        logger = logging.getLogger('')
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    
    app.run()
    
    job_manager = get_global_job_manager()
    if job_manager is not None:
        job_manager.shutdown()
