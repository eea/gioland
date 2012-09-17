from StringIO import StringIO
import subprocess
import json
from functools import wraps
from fabric.api import *
from fabric.contrib.files import exists
from path import path
import imp


def create_sarge_deployer(name, deployer_env):
    from blinker import Namespace
    from blinker.base import symbol

    deployer = imp.new_module('_sarge_deployer.{name}'.format(**locals()))
    deployer.env = deployer_env
    deployer.app_options = {}
    deployer.default_app = None
    deployer.signal_ns = Namespace()
    deployer.install = deployer.signal_ns.signal('install')
    deployer.has_started = deployer.signal_ns.signal('has_started')
    deployer.promote = deployer.signal_ns.signal('promote')
    deployer.will_stop = deployer.signal_ns.signal('will_stop')

    def _func(func):
        setattr(deployer, func.__name__, func)
        return func

    deployer._func = _func

    @deployer._func
    def _task(func):
        @deployer._func
        @task
        @wraps(func)
        def wrapper(*args, **kwargs):
            with settings(**deployer.env):
                return func(*args, **kwargs)

        return wrapper

    @deployer._func
    def quote_json(config):
        return "'" + json.dumps(config).replace("'", "\\u0027") + "'"

    @deployer._func
    def on(signal_name, app_name='ANY'):
        signal = deployer.signal_ns[signal_name]
        def decorator(func):
            def wrapper(*args, **kwargs):
                return func()
            signal.connect(wrapper, symbol(app_name), False)
            return func
        return decorator

    @deployer._func
    def add_application(app_name, **options):
        if deployer.default_app is None:
            deployer.default_app = app_name
        deployer.app_options[app_name] = options

    def _sarge_cmd(cmd):
        return "{sarge_home}/bin/sarge {cmd}".format(cmd=cmd, **env)

    def _sarge(cmd):
        return run(_sarge_cmd(cmd))

    def _new():
        instance_config = {
            'application_name': env['deployer_app_name'],
        }
        instance_config.update(env.get('sarge_instance_config', {}))
        out = _sarge("new " + deployer.quote_json(instance_config))
        sarge_instance = out.strip()
        return sarge_instance

    def _destroy_instance(sarge_instance):
        with settings(sarge_instance=sarge_instance):
            deployer.will_stop.send(symbol(env['deployer_app_name']))
            _sarge("destroy {sarge_instance}".format(**env))

    def _remove_instances(keep=None):
        for other_instance in _instances():
            if other_instance['id'] == keep:
                continue
            with settings(sarge_instance=other_instance['id']):
                app_name = other_instance['meta']['APPLICATION_NAME']
                deployer.will_stop.send(symbol(app_name))
                _destroy_instance(other_instance['id'])

    def _simple_deploy():
        _remove_instances()
        sarge_instance = _new()
        instance_dir = env['sarge_home'] / sarge_instance
        with settings(sarge_instance=sarge_instance,
                      instance_dir=instance_dir):
            deployer.install.send(symbol(env['deployer_app_name']))
            _sarge("start {sarge_instance}".format(**env))
            deployer.has_started.send(symbol(env['deployer_app_name']))
            deployer.promote.send(symbol(env['deployer_app_name']))

    def _instances():
        app_name = env['deployer_app_name']
        for instance in json.loads(_sarge('list'))['instances']:
            if instance['meta']['APPLICATION_NAME'] != app_name:
                continue
            yield instance

    @deployer._task
    def deploy(app_name=None):
        if app_name is None:
            app_list = deployer.app_options.keys()
            if len(app_list) == 1:
                [app_name] = app_list
            else:
                print "Available applications: %r" % app_list
                return
        with settings(deployer_app_name=app_name):
            _simple_deploy()

    @deployer._task
    def shell(sarge_instance=None):
        if sarge_instance is None:
            sarge_instance = deployer.default_app
        open_shell("exec " + _sarge_cmd("run " + sarge_instance))

    @deployer._task
    def supervisorctl():
        open_shell("exec {sarge_home}/bin/supervisorctl".format(**env))

    return deployer


env['use_ssh_config'] = True
if not env['hosts']:
    env['hosts'] = ['gaur']

SARGE_HOME = path('/var/local/gioland/workflow')
PYTHON_PREFIX = SARGE_HOME / 'opt' / 'Python-2.7.3'

gioland = create_sarge_deployer('gioland', {
        'sarge_home': SARGE_HOME,
        'sarge_instance_config': {'prerun': 'sarge_rc.sh'},
        'gioland_python_prefix': PYTHON_PREFIX,
        'gioland_venv': SARGE_HOME / 'opt' / 'gioland-venv',
        'gioland_port': '42023',
    })

gioland.add_application('web')
_gioland_env = gioland.env
_quote_json = gioland.quote_json


@task
def virtualenv():
    with settings(**_gioland_env):
        if not exists(env['gioland_venv']):
            run("{gioland_python_prefix}/bin/virtualenv "
                "--distribute --no-site-packages "
                "{gioland_venv}"
                .format(**env))

        put("requirements.txt", str(env['gioland_venv']))
        run("{gioland_venv}/bin/pip install -r {gioland_venv}/requirements.txt"
            .format(**env))


@gioland.on('install', 'web')
def install():
    src = subprocess.check_output(['git', 'archive', 'HEAD'])
    put(StringIO(src), str(env['instance_dir'] / '_src.tar'))
    with cd(env['instance_dir']):
        try:
            run("tar xvf _src.tar")
        finally:
            run("rm _src.tar")

    run("mkdir {instance_dir}/instance".format(**env))

    put(StringIO(("source {gioland_venv}/bin/activate\n").format(**env)),
        str(env['instance_dir'] / 'sarge_rc.sh'))

    app_name = env['deployer_app_name']

    put(StringIO("#!/bin/bash\n"
                 "exec python manage.py runcherrypy -p {gioland_port}\n"
                 .format(**env)),
        str(env['instance_dir'] / 'server'),
        mode=0755)


# remap tasks to top-level namespace
deploy = gioland.deploy
supervisorctl = gioland.supervisorctl
shell = gioland.shell
del gioland


@task
def ssh():
    open_shell()
