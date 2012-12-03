import os
import subprocess
from StringIO import StringIO
from fabric.api import *

_host, _directory = os.environ['TARGET'].split(':')
env['hosts'] = [_host]
env['target_directory'] = _directory
env['use_ssh_config'] = True


@task
def ssh():
    open_shell()


@task
def upload_docs():
    local_html = path(__file__).parent / 'docs' / '_build' / 'html'
    remote_dir = SARGE_HOME / 'var' / 'gioland-docs'
    upload_project(str(local_html), str(remote_dir))


@task
def deploy():
    tarball = subprocess.check_output(['git', 'archive', 'HEAD'])
    with cd(env['target_directory']):
        put(StringIO(tarball), '_app.tar')
        try:
            run('bin/sarge deploy _app.tar web')
        finally:
            run('rm _app.tar')
