# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
App Launch Hook

This hook is executed to launch the applications.
"""

import os
import sys
import subprocess
import platform
import tank



ENGINES = {
    'tk-houdini' : 'houdini',
    'tk-maya' : 'maya',
    'tk-nuke' : 'nuke',
    'tk-nukestudio' : 'nuke',
    'tk-mari' : 'mari',
    'tk-clarisse' : 'clarisse',
    'tk-unreal' : 'unreal'
}



class AppLaunch(tank.Hook):
    """
    Hook to run an application.
    """

    def execute(
        self, app_path, app_args, version, engine_name, software_entity=None, **kwargs
    ):
        """
        The execute function of the hook will be called to start the required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.
        :param software_entity: (dict) If set, this is the Software entity that is
            associated with this launch command.

        :returns: (dict) The two valid keys are 'command' (str) and 'return_code' (int).
        """

        system = platform.system()

        app_name = ENGINES[engine_name]
        context = self.tank.context_from_path(self.tank.project_path)
        sg = self.tank.shotgun
        project = context.project
        user = context.user
        depart = sg.find_one("Department", [['users', 'in', user]], ['name'])

        # Handle UE special case for Python 3
        if sys.version_info.major == 3 and app_name == 'unreal' and system == 'Windows':
            now_dir = os.path.dirname(os.path.abspath(__file__))
            packages = os.path.join(now_dir, 'packages', 'win')
            sys.path.append(packages)

        # Default launch logic
        if tank.util.is_linux():
            cmd = "%s %s &" % (app_path, app_args)

        elif tank.util.is_macos():
            if app_path.endswith(".app"):
                cmd = 'open -n -a "%s"' % (app_path)
                if app_args:
                    cmd += " --args %s" % app_args
            else:
                cmd = "%s %s &" % (app_path, app_args)

        else:  # Windows
            cmd = 'start /B "App" "%s" %s' % (app_path, app_args)

        # Run the command to launch the app
        exit_code = os.system(cmd)
        return {"command": cmd, "return_code": exit_code}
