
import os
import pandas as pd
from typing import List, Dict, Union
import commune as c

class Docker(c.Module): 
    @classmethod
    def dockerfile(cls, path = c.repo_path): 
        path =  [f for f in c.ls(path) if f.endswith('Dockerfile')][0]
        return c.get_text(path)
    
    @classmethod
    def resolve_repo_path(cls, path):

        if path is None:
            path = c.repo_path
        else:
            if not path.startswith('/') or not path.startswith('~') or not path.startswith('.'):
                path = c.repo_path + '/' + path
            else:
                path = os.path.abspath(path)
        return path

    @classmethod
    def resolve_docker_compose_path(cls,path = None):
        path = cls.resolve_repo_path(path)
        return [f for f in c.ls(path) if 'docker-compose' in os.path.basename(f)][0]
        return path

    @classmethod
    def docker_compose(cls, path = c.repo_path): 
        docker_compose_path = cls.resolve_docker_compose_path(path)
        return c.load_yanl(docker_compose_path)

    @classmethod
    def resolve_docker_path(cls, path = None):
        path = cls.resolve_repo_path(path)
        return [f for f in c.ls(path) if 'Dockerfile' in os.path.basename(f)][0]
        return path
    
    @classmethod
    def build(cls, path , tag = None , sudo=False, verbose=True, env={'DOCKER_BUILDKIT':'1'}):

        path = cls.resolve_docker_path(path)
        if tag is None:
            tag = path.split('/')[-2]

        return c.cmd(f'docker build -t {tag} .', sudo=sudo, env=env,cwd=os.path.dirname(path),  verbose=verbose)
    @classmethod
    def kill(cls, name, sudo=False, verbose=True):
        c.cmd(f'docker kill {name}', sudo=sudo, verbose=verbose)
        c.cmd(f'docker rm {name}', sudo=sudo, verbose=verbose)
        return {'status': 'killed', 'name': name}
    @classmethod
    def rm(cls, name, sudo=False, verbose=True):
        c.cmd(f'docker rm {name}', sudo=sudo, verbose=verbose)
        return {'status': 'removed', 'name': name}

    @classmethod
    def exists(cls, name:str):
        return name in cls.ps()

    @classmethod
    def rm_sudo(cls, sudo:bool=True, verbose:bool=True):
        '''
        To remove the requirement for sudo when using Docker, you can configure Docker to run without superuser privileges. Here's how you can do it:
        Create a Docker group (if it doesn't exist) and add your user to that group:
        bash
        Copy code
        sudo groupadd docker
        sudo usermod -aG docker $USER
        return c.cmd(f'docker rm -f {name}', sudo=True)
        '''
        c.cmd(f'groupadd docker', sudo=sudo, verbose=verbose)
        c.cmd(f'usermod -aG docker $USER', sudo=sudo, verbose=verbose)
        c.cmd(f'chmod 666 /var/run/docker.sock', sudo=sudo, verbose=verbose)



    

    @classmethod
    def containers(cls,  sudo:bool = False):
        return [container['name'] for container in cls.ps(sudo=sudo)]
    
    @classmethod 
    def chmod_scripts(cls):
        c.cmd(f'bash -c "chmod +x {c.libpath}/scripts/*"', verbose=True)



    def install_gpus(self):
        self.chmod_scripts()
        c.cmd('./scripts/nvidia_docker_setup.sh', cwd=c.libpath, verbose=True,bash=True)

    def install(self):
        self.chmod_scripts()
        c.cmd('./scripts/install_docker.sh', cwd=c.libpath, verbose=True,bash=True)


    @classmethod
    def install_docker_compose(cls, sudo=False):
        return c.cmd('apt install docker-compose', verbose=True, sudo=True)
    # def build_commune(self, sudo=False):
    #     self.build(path=self.libpath, sudo=sudo)

    @classmethod
    def build(cls,path:str = None, tag:str = None,  sudo=False):
        path = cls.resolve_dockerfile(path)

        if tag is None:
            tag = path.split('/')[-2]
        assert tag is not None, 'tag must be specified'

        cmd = f'docker build -t {tag} .'
        dockerfile_dir = os.path.dirname(path)

        c.cmd(cmd,cwd = dockerfile_dir, env={'DOCKER_BUILDKIT':'1'}, verbose=True, sudo=sudo, bash=False)

    @classmethod
    def images(cls, df=True):
        text = c.cmd('docker images', verbose=False)
        if df:
            df = []
            cols = []
            for i, l in enumerate(text.split('\n')):
                if len(l) > 0:
                    if i == 0:
                        cols = [_.strip().replace(' ', '_') for _ in l.split('  ') if len(_) > 0]
                    else:
                        df.append([_.strip() for _ in l.split('  ') if len(_) > 0])
            df = pd.DataFrame(df, columns=cols)    
            return df
        
        return [l.split(' ')[0] for l in text.split('\n') if len(l) > 0][1:]


    @classmethod
    def run(cls, 
                    image : str,
                    cmd : str  = 'ls',
                    volumes:List[str] = None,
                    name: str = None,
                    gpus:list=False,
                    shm_size : str='100g',
                    sudo:bool = False,
                    build:bool = True,
                    ports:Dict[str, int]=None,
                    net : str = 'host',
                    daemon:bool = True,
                    run: bool = True):
        
        '''
        Arguments:

        '''
        if name is None:
            name = image

        docker_cmd = f'docker run'


        docker_cmd += f' --net {net} '

        if build:
            cls.build(image, tag=name)
        
        if daemon:
            docker_cmd += ' -d '

        if isinstance(gpus, list):
            gpus = ','.join(map(str, gpus))  
            docker_cmd += f' --gpus \'"device={gpus}"\''   
        elif isinstance(gpus, str):
            docker_cmd += f' --gpus "{gpus}"'
        else:
            pass
            
        
        # ADD THE SHM SIZE
        if shm_size != None:
            docker_cmd += f' --shm-size {shm_size}'
        
        if ports != None:
            for external_port, internal_port in ports.items():
                docker_cmd += f' -p {external_port}:{internal_port}'

        # ADD THE VOLUMES
        if volumes is not None:
            if isinstance(volumes, str):
                volumes = [volumes]
            if isinstance(volumes, list):
                docker_cmd += ' '.join([f' -v {v}' for v in volumes])
            elif isinstance(volumes, dict):
                for v_from, v_to in volumes.items():
                    docker_cmd += f' -v {v_from}:{v_to}'

        docker_cmd += f' --name {name} {image}'


        if cmd is not None:
            docker_cmd += f' bash -c "{cmd}"'
        
        c.print(docker_cmd)
        # text_output =  c.cmd(docker_cmd, sudo=sudo, output_text=True)

        # if 'Conflict. The container name' in text_output:
        #     contianer_id = text_output.split('by container "')[-1].split('". You')[0].strip()
        #     c.cmd(f'docker rm -f {contianer_id}', verbose=True)
        #     text_output = c.cmd(docker_cmd, verbose=True)
        





        # self.update()
       
    
    @classmethod
    def psdf(cls, load=True, save=False, keys = [ 'container_id', 'names', 'ports'], idx_key ='container_id'):
        output_text = c.cmd('docker ps', verbose=False)

        rows = []
        for i, row in enumerate(output_text.split('\n')[:-1]):
            if i == 0:
                columns = [l.lower().strip().replace(' ', '_') for l in row.split('   ') if len(l) > 0]
            else:
                NA_SPACE = "           "
                if len(row.split(NA_SPACE)) > 1:
                    row_splits = row.split(NA_SPACE)
                    row = row_splits[0] + '  NA  ' + ' '.join(row_splits[1:])
                row = [_.strip() for _ in row.split('  ') if len(_) > 0]
                rows.append(row)

        df = pd.DataFrame(rows, columns=columns)
        df['ports'] = df['ports'].apply(lambda x: x.split('->')[0].strip() if len(x.split('->')) > 1 else x)
        df = df[keys]
        df.set_index(idx_key, inplace=True)
        return df   

    @classmethod
    def ps(cls, path = None):
        df = cls.psdf()
        paths =  df['names'].tolist()
        if path != None:
            paths = [p for p in paths if path in p]

        return paths
    


    @classmethod
    def dockerfiles(cls, path = None):
       if path is None:
           path = c.libpath + '/'
       return [l for l in c.walk(path) if l.endswith('Dockerfile')]
    
    @classmethod
    def name2dockerfile(cls, path = None):
       return {l.split('/')[-2] if len(l.split('/'))>1 else c.lib:l for l in cls.dockerfiles(path)}
    
    
    @classmethod
    def resolve_dockerfile(cls, name):
        if name == None:
            name = 'commune'
        
        if c.exists(name):
            return name
        name2dockerfile = cls.name2dockerfile()
        if name in name2dockerfile:
            return name2dockerfile[name]
        else:
            raise ValueError(f'Could not find docker file for {name}')
        
    get_dockerfile = resolve_dockerfile


    



    @classmethod
    def compose_paths(cls, path = None):
       if path is None:
           path = c.libpath + '/'
       return [l for l in c.walk(path) if l.endswith('docker-compose.yaml') or l.endswith('docker-compose.yml')]
    
    @classmethod
    def name2compose(cls, path=None):
        compose_paths = cls.compose_paths(path)
        return {l.split('/')[-2] if len(l.split('/'))>1 else c.lib:l for l in compose_paths}
    
    @classmethod
    def get_compose_path(cls, path:str):
        path = cls.name2compose().get(path, path)
        return path

    @classmethod
    def get_compose(cls, path:str):
        path = cls.get_compose_path(path)
        return c.load_yaml(path)

    @classmethod
    def put_compose(cls, path:str, compose:dict):
        path = cls.get_compose_path(path)
        return c.save_yaml(path, compose)
    

    # @classmethod
    # def down(cls, path='frontend'):
    #     path = cls.get_compose_path(path)
    #     return c.cmd('docker-compose -f {path} down', verbose=True)



    @classmethod
    def compose(cls, 
                path: str,
                compose: Union[str, dict, None] = None,
                daemon:bool = True,
                verbose:bool = True,
                dash:bool = True,
                cmd : str = None,
                build: bool = False,
                project_name: str = None,
                cwd : str = None,
                down: bool = False
                ):
 

        cmd = f'docker-compose' if dash else f'docker compose'

        path = cls.get_compose_path(path)
        if compose == None:
            compose = cls.get_compose(path)
        
        if isinstance(path, str):
            compose = cls.get_compose(path)
        

        if project_name != None:
            cmd += f' --project-name {project_name}'
        c.print(f'path: {path}', verbose=verbose)
        tmp_path = path + '.tmp'
        cmd +=  f' -f {tmp_path} up'

        if daemon:
            cmd += ' -d'


        c.print(f'cmd: {cmd}', verbose=verbose)
        # save the config to the compose path
        c.print(compose)
        c.save_yaml(tmp_path, compose)
        if cwd is None:
            assert os.path.exists(path), f'path {path} does not exist'
            cwd = os.path.dirname(path)
        if build:
            c.cmd(f'docker-compose -f {tmp_path} build', verbose=True, cwd=cwd)
            
        text_output = c.cmd(cmd, verbose=True)

        if 'Conflict. The container name' in text_output:
            contianer_id = text_output.split('by container "')[-1].split('". You')[0].strip()
            c.cmd(f'docker rm -f {contianer_id}', verbose=True)
            text_output = c.cmd(cmd, verbose=True)

        if "unknown shorthand flag: 'f' in -f" in text_output:
            cmd = cmd.replace('docker compose', 'docker-compose')
            text_output = c.cmd(cmd, verbose=True)

        c.rm(tmp_path)
    @classmethod
    def rm_container(self, name):
        c.cmd(f'docker rm -f {name}', verbose=True)

    @classmethod
    def logs(cls, name, sudo=False, follow=False, verbose=False, tail:int=100):
        cmd = f'docker  logs {name} {"-f" if follow else ""} --tail {tail}'
        return c.cmd(cmd, verbose=verbose)

    @classmethod
    def tag(cls, image:str, tag:str):
        c.cmd(f'docker tag {image} {tag}', verbose=True)
        c.cmd(f'docker push {tag}', verbose=True)
    @classmethod
    def login(self, username:str, password:str):
        c.cmd(f'docker login -u {username} -p {password}', verbose=True)

    @classmethod
    def logout(self, image:str):
        c.cmd(f'docker logout {image}', verbose=True)

