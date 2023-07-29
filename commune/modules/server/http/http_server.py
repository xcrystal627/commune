
from typing import Dict, List, Optional, Union
import commune as c
import torch 




class HTTPServer(c.Module):
    access_modes = ['public', 'root', 'subspace']
    def __init__(
        self,
        module: Union[c.Module, object],
        name: str = None,
        ip: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[int] = 4,
        verbose: bool = True,
        whitelist: List[str] = None,
        blacklist: List[str] = None,
        access:str = 'public',
        sse: bool = False,
        max_history: int = 100,
        save_history_interval: int = 100,
        max_request_staleness: int = 100,
        key = None,
        root_key = None,
    ) -> 'Server':
        self.sse = sse
        self.root_key = c.get_key(root_key)
        self.timeout = timeout
        self.verbose = verbose
        self.serializer = c.module('server.http.serializer')()
        self.ip = c.resolve_ip(ip, external=False)  # default to '0.0.0.0'
        self.port = c.resolve_port(port)
        self.address = f"{self.ip}:{self.port}"
        self.set_access(access)
        


        # KEY FOR SIGNING DATA
        self.key = c.get_key(name) if key == None else key

        # WHITE AND BLACK LIST FUNCTIONS
        
        self.whitelist = getattr( module, 'whitelist', []) if whitelist == None else whitelist
        self.blacklist = getattr( module, 'blacklist', []) if blacklist == None else blacklist
        self.save_history_interval = save_history_interval
        self.max_request_staleness = max_request_staleness
        self.history = []
        # ensure that the module has a name

        if isinstance(module, str):
            module = c.module(module)()
        elif isinstance(module, type):
            module = module()

        if name == None:
            name = module.name()

        self.name = name
        for k in ['module_name', 'module_id', 'name']:
            if k not in module.__dict__:
                module.__dict__[k] = name
        # register the server
        module.ip = self.ip
        module.port = self.port
        module.address  = self.address
        self.module = module
        self.set_api(ip=self.ip, port=self.port)
        self.serve()

    def set_access(self, access: str) -> None:
        assert access in self.access_modes, f"Access mode must be one of {self.access_modes}"
        self.access = access

    def state_dict(self) -> Dict:
        return {
            'ip': self.ip,
            'port': self.port,
            'address': self.address,
            'timeout': self.timeout,
            'verbose': self.verbose,
        }


    def test(self):
        r"""Test the HTTP server.
        """
        # Test the server here if needed
        c.print(self.state_dict(), color='green')
        return self
    
    def verify_access(self, input) -> bool:
        if self.access != 'public':
            assert isinstance(input, dict), f"Data must be a dict, not {type(data)}"
            assert 'data' in input, f"Data not included"
            assert 'signature' in input, f"Data not signed"
            assert self.key.verify(input), f"Data not signed with correct key"
            address = input.get('address', None)


            if self.access == 'root':
                assert address == self.root_key.ss58_address, f"Data not signed with correct key"
            else:
                raise NotImplementedError(f"Access mode {self.access} not implemented")
            
        else:
            return True


    
    def process_input(self, input: dict) -> bool:
        r""" Verify the data is signed with the correct key.
        """
        try:
            self.verify_access(input)
            data = self.serializer.deserialize(input.pop('data'))

            if self.access != 'public':
                request_timestamp = data.get('timestamp', 0)
                request_staleness = c.timestamp() - request_timestamp
                assert request_staleness < self.max_request_staleness, f"Request is too old, {request_staleness} > MAX_STALENESS ({self.max_request_staleness})  seconds old"



            return data
        except Exception as e:
            c.print(e, color='red')
            return {'error': str(e)}
        
    @staticmethod
    def event_source_response(generator):
        from sse_starlette.sse import EventSourceResponse
        return EventSourceResponse(generator)
    
    @staticmethod
    def resolve_generator(self, generator):

        def generator_wrapper():
            if c.is_generator(generator):
                for item in generator:
                    yield self.process_result(item, resolve_generator=False)
            else: 
                yield self.process_result(generator, resolve_generator=False)

        return generator_wrapper
    
    def process_result(self,  result):
        if self.sse == True:
            # if we are using sse, we want to include one time calls too
            result = self.resolve_generator(self, result)
            return self.event_source_response(result)
        else:
            # if we are not using sse then we want to convert the generator to a list
            # WARNING : This will not work for infinite loops lol because it will never end
            if c.is_generator(result):
                result = list(result)
            
        # serialize result
        result = self.serializer.serialize(result)
        
        # sign result data (str)
        result =  self.key.sign(result, return_json=True)

        return result
    def set_api(self, ip = None, port = None):
        ip = self.ip if ip == None else ip
        port = self.port if port == None else port
        from fastapi import FastAPI
        

        self.app = FastAPI()

        @self.app.post("/{fn}")
        async def forward_api(fn:str, input:dict[str, str]):

            try:
                # verify key
                data = self.process_input(input)
                # forward
                result =  self.forward(fn=fn, 
                                        args=data.get('args', []), 
                                        kwargs=data.get('kwargs', {})
                                        )

                result = self.process_result(result)

            except Exception as e:
                c.print(e, color='red')
                result = {'error': str(e)}


            # send result to client
            return result
        
        



    def save(self, data: dict):
        r"""Save the history of the server.
        """
        og_history = self.get(f'history/{self.name}', [])
        og_history.extend(self.history)
    def serve(self, **kwargs):
        import uvicorn

        try:
            c.register_server(name=self.name, ip=self.ip, port=self.port)

            uvicorn.run(self.app, host=self.ip, port=self.port)
        except Exception as e:
            c.print(e, color='red')
            c.deregister_server(self.name)
        finally:
            c.deregister_server(self.name)
        

    def forward(self, fn: str, args: List = None, kwargs: Dict = None, **extra_kwargs):
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        obj = getattr(self.module, fn)
        if callable(obj):
            response = obj(*args, **kwargs)
        else:
            response = obj
        return response


    def __del__(self):
        c.deregister_server(self.name)

