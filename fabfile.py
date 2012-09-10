from StringIO import StringIO
import subprocess
from fabric.api import *
from fabric.contrib.files import exists
from path import path


env.update({
    'use_ssh_config': True,
    'python_prefix': path('/var/local/gioland/workflow/Python-2.7.3'),
    'sarge_home': path('/var/local/gioland/workflow/sarge'),
    'gioland_venv': path('/var/local/gioland/workflow/sarge/var/gioland-venv'),
})

if not env['hosts']:
    env['hosts'] = ['gaur']


def sarge(cmd):
    sarge_base = ("'%(sarge_home)s/venv/bin/sarge' "
                  "'%(sarge_home)s' " % env)
    return run(sarge_base + cmd)


def version_paths(version_folder):
    return {
        'gioland_version_folder': version_folder,
        'gioland_version_instance': version_folder/'instance',
    }


@task
def ssh():
    open_shell()


@task
def virtualenv():
    if not exists(env['gioland_venv']):
        run("'%(python_prefix)s/bin/virtualenv' '%(gioland_venv)s'" % env)

    put("requirements.txt", str(env['gioland_venv']))
    run("%(gioland_venv)s/bin/pip install "
        "-r %(gioland_venv)s/requirements.txt"
        % env)


@task
def install():
    src = subprocess.check_output(['git', 'archive', 'HEAD'])
    run("mkdir {gioland_version_instance}".format(**env))
    put(StringIO(src), str(env['gioland_version_folder'] / '.src.tar'))
    with cd(env['gioland_version_folder']):
        try:
            run("tar xvf .src.tar")
        finally:
            run("rm .src.tar")

    if not exists(env['gioland_version_instance']):
        run("mkdir -p '%s'" % env['gioland_version_instance'])

    put(StringIO("exec %(gioland_venv)s/bin/python "
                 "%(gioland_version_folder)s/manage.py $@\n" % env),
        str(env['gioland_version_folder']/'manage.sh'), mode=0755)

    put(StringIO("exec %(gioland_version_folder)s/manage.sh "
                 "runcherrypy -p 42023\n" % env),
        str(env['gioland_version_folder']/'start.sh'), mode=0755)

    put(StringIO("{}"), str(env['gioland_version_folder']/'sargeapp.yaml'))


@task
def deploy():
    version_folder = path(sarge("new_version gioland"))
    with settings(**version_paths(version_folder)):
        execute('install')
    sarge("activate_version gioland '%s'" % version_folder)
