import commune as c
from text_generation import Client
class TextGenerator(c.Module):
    image = 'text_generator'
    
    def serve(self,tag = None,
                    num_shard=2, 
                    gpus='all',
                    shm_size='100g',
                    volume=None, 
                    build:bool = True,
                    port=None):
        model = self.config.model
        name =  self.image +"_"+ model

        if tag != None:
            name = f'{name}_{tag}'
        

        model_id = self.config.shortcuts.get(model, model)
        
        if port == None:
            port = c.resolve_port(port)

        if volume == None:
            volume = self.resolve_path('data')
            c.mkdir(volume)
        # if build:
        #     self.build(tag=tag)
        cmd_args = f'--num-shard {num_shard} --model-id {model_id}'
        cmd = f'docker run -d --gpus \'"device={gpus}"\' --shm-size {shm_size} -p {port}:80 -v {volume}:/data --name {name} {self.image} {cmd_args}'

        output_text = c.cmd(cmd, sudo=True, output_text=True)
        if 'Conflict. The container name' in output_text:
            c.print(f'container {name} already exists, restarting...')
            contianer_id = output_text.split('by container "')[-1].split('". You')[0].strip()
            c.cmd(f'docker rm -f {contianer_id}', sudo=True, verbose=True)
            c.cmd(cmd, sudo=True, verbose=True)
    # def fleet(self, num_shards = 2, buffer=5_000_000_000, **kwargs):
    #     model_size = c.get_model_size(self.config.model)
    #     model_shard_size = (model_size // num_shards ) + buffer
    #     max_gpu_memory = c.max_gpu_memory(model_size)
    #     c.print(max_gpu_memory, model_shard_size)


    #     c.print(gpus)


        
        

    def build(self):
        cmd = f'sudo docker build -t {self.image} .'
        c.cmd(cmd, cwd=self.dirpath(), verbose=True)

    def logs(self, name):
        return c.cmd(f'sudo docker logs {name}', cwd=self.dirpath())


    def namespace(self):
        output_text = c.cmd('sudo docker ps')
        names = [l.split('  ')[-1].strip() for l in output_text.split('\n')[1:-1]]
        addresses = [l.split('  ')[-2].split('->')[0].strip() for l in output_text.split('\n')[1:-1]]
        namespace = {k:v for k,v in  dict(zip(names, addresses)).items() if k.startswith(self.image)}
        return namespace

    
    def servers(self):
        return list(self.namespace().keys())
    
    def addresses(self):
        return list(self.namespace().values())
    
    def random_server(self):
        return c.choice(self.servers())
    
    def random_address(self):
        return c.choice(self.addresses())

    
    def install(self):
        c.cmd('pip install -e clients/python/', cwd=self.dirpath(), verbose=True)


    @classmethod
    def generate(cls, 
                prompt = 'what is up', 
                max_new_tokens:int=100, 
                model:str = None, 
                timeout = 6,
                **kwargs):

        self = cls()
                
        if model != None:
            address = self.namespace()[model]
        else:
            address = self.random_address()
        c.print(f'generating from {address}')

        client = Client('http://'+address)
        generated_text = client.generate_stream(prompt, max_new_tokens=max_new_tokens, **kwargs)
        output_text = ''

        start_time = c.time()
        for text_obj in generated_text:
            if c.time() - start_time > timeout:
                break
            text =  text_obj.token.text
            output_text += text
            c.print(text, end='')


        return output_text

    talk = generate

    