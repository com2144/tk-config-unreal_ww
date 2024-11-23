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

        depart_confirm = False

        if (depart['name'] == 'RND' and engine_name == 'tk-nuke') or depart['name'] in ['General']:
            depart_confirm = True


        if sys.version_info.major == 3 and app_name == 'unreal' and system == 'Windows':
            now_dir = os.path.dirname(os.path.abspath(__file__))
            packages = os.path.join(now_dir, 'packages', 'win')

            sys.path.append(packages)

        if depart_confirm:
            adapter = get_adapter(platform.system())
            packages = get_rez_packages(sg, app_name, version, system, project)

            try:
                import rez as _
            except ImportError:
                rez_path = adapter.get_rez_module_root()
                if not rez_path:
                    raise EnvironmentError('rez is not installed and could not be automatically found. Cannot continue.')
                
                if sys.version_info.major == 3:
                    rez_path = rez_path.decode('utf-8')
                
                sys.path.append(rez_path)
            
            from rez import resolved_context

            if not packages or app_name == 'unreal':
                if not packages:
                    self.logger.debug('No rez packages were found. The default boot, instead.')
                command = adapter.get_command(app_path, app_args)
                return_code = os.system(command)
                return {'command': command, 'return_code': return_code}
            
            context = resolved_context.ResolvedContext(packages)
            return adapter.execute(context, app_args, app_name)

        else:
            if tank.util.is_linux():
                # on linux, we just run the executable directly
                cmd = "%s %s &" % (app_path, app_args)

            elif tank.util.is_macos():
                # If we're on OS X, then we have two possibilities: we can be asked
                # to launch an application bundle using the "open" command, or we
                # might have been given an executable that we need to treat like
                # any other Unix-style command. The best way we have to know whether
                # we're in one situation or the other is to check the app path we're
                # being asked to launch; if it's a .app, we use the "open" command,
                # and if it's not then we treat it like a typical, Unix executable.
                if app_path.endswith(".app"):
                    # The -n flag tells the OS to launch a new instance even if one is
                    # already running. The -a flag specifies that the path is an
                    # application and supports both the app bundle form or the full
                    # executable form.
                    cmd = 'open -n -a "%s"' % (app_path)
                    if app_args:
                        cmd += " --args %s" % app_args
                else:
                    cmd = "%s %s &" % (app_path, app_args)

            else:
                # on windows, we run the start command in order to avoid
                # any command shells popping up as part of the application launch.
                cmd = 'start /B "App" "%s" %s' % (app_path, app_args)

            # run the command to launch the app
            exit_code = os.system(cmd)

            return {"command": cmd, "return_code": exit_code}


def get_rez_packages(sg, app_name, version, system, project):
    
    if system == 'Linux':
        filter_dict = [['code','is',app_name.title()+" "+version],
                       ['projects','in',project]
                      ]
        packages = sg.find("Software",filter_dict,['sg_rez'])
        if packages : 
            packages =  packages[0]['sg_rez']
        else:
            filter_dict = [['code','is',app_name.title()+" "+version],
                        ['projects','is',None] ]
            packages = sg.find("Software",filter_dict,['sg_rez'])
            if packages:
                packages =  packages[0]['sg_rez']

    else:
        filter_dict = [['code','is',app_name.title()+" "+version],
                       ['projects','in',project]
                      ]
        packages = sg.find("Software",filter_dict,['sg_win_rez'])
        if packages : 
            packages =  packages[0]['sg_win_rez']
        else:
            filter_dict = [['code','is',app_name.title()+" "+version],
                        ['projects','is',None] ]
            packages = sg.find("Software",filter_dict,['sg_win_rez'])
            if packages:
                packages =  packages[0]['sg_win_rez']

    if packages:
        packages = [ x for x in packages.split(",")] 
    else:
        packages = None
        
    return packages



def get_adapter(system=''):
    if not system:
        system = platform.system()
    
    options = {
        'Linux' : LinuxAdapter,
        'Windows' : WindowsAdapter
        }

    try :
        return options[system]

    except KeyError:
        raise NotImplementedError('system "{system}" is currently unsupported. Options were, "{options}"'
                                  ''.format(system=system, options=list(options)))
    

class BaseAdapter:

    shell_type = 'bash'

    @staticmethod
    def get_command(path, args):
        return 'mate-terminal -x bash -c "{path}" {args} &'.format(path=path, args=args)

    @staticmethod
    def get_rez_root_command():

        return 'rez-env rez -- printenv REZ_REZ_ROOT'

    @classmethod
    def get_rez_module_root(cls):

        command = cls.get_rez_root_command()
        module_path, stderr = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()

        module_path = module_path.strip()

        if not stderr and module_path:
            return module_path

        return ''

    @classmethod
    def execute(cls, context, args, command):

        os.environ['USE_SHOTGUN'] = "OK"

        if args:
            command += ' {args}'.format(args=args)
        
        if platform.system() == 'Linux':
            command = "mate-terminal -x bash -c '{}' &".format(command)
        else:
            command = "start /B 'App' '{}'".format(command)

        context.execute_shell(
            command = command,
            stdin = False,
            block = False
        )

        return_code = 0
        context.print_info(verbosity=True)

        return {
            'command': command,
            'return_code': return_code,
        }


class LinuxAdapter(BaseAdapter):

    pass


class WindowsAdapter(BaseAdapter):

    shell_type = 'cmd'

    @staticmethod
    def get_command(path, args):
        return 'start /B "App" "{path}" {args}'.format(path=path, args=args)

    @staticmethod
    def get_rez_root_command():

        return 'rez-env rez -- echo %REZ_REZ_ROOT%'
