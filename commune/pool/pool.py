import queue
import commune as c
import threading
import multiprocessing

class Pool(c.Module):
    def __init__(self, **kwargs):

        self.run_loop = True
        self.init(**kwargs)
        self.add_workers()
        
        
        
    def resolve_queue_name(self, name = None):
        if name is None:
            name = f'Q::{len(self.workers)}'
            
        assert isinstance(name, str)
        
        return name
        
        
    def add_queue(self, name = None, mode='thread', update:bool=False):
        if not hasattr(self, 'queue'):
            self.queue = self.munch({})
        
        name = self.resolve_queue_name(name)
        if name in self.queue and not update:
            return self.queue[name]
        
        
        if mode == 'thread':
            self.queue[name] = queue.Queue()
        else:
            raise NotImplemented(mode)
        
    def add_queues(self, *names,  **kwargs):
        for name in names:
            self.add_queue(name, **kwargs)
        
    def resolve_worker_name(self, name = None):
        if name is None:
            name = f'W::{len(self.workers)}'
        else:
            name = str(name)
        assert isinstance(name, str)
        assert name not in self.workers
        return name
      
    def add_workers(self, *names, **kwargs):
        if len(names) == 0:
            names = [self.resolve_worker_name(i) for i in range(self.config.num_workers)]
        for name in names:
            self.add_worker(name, out_queue= 'background', **kwargs)
            
        # add background worker
        self.add_worker(name='background', 
                        fn=self.background_fn, 
                        in_queue='background',
                        out_queue='output',
                        **kwargs)
        
        
        
    @property
    def workers(self):
        return self.config.get('workers', {})
    @workers.setter
    def workers(self, value):
        self.config['workers'] = value
        return value
    
    @property
    def mode(self):
        return self.config.get('mode', {})
    @workers.setter
    def mode(self, value):
        self.config['mode'] = value
        return value
        
        
    def resolve_mode(self, mode = None):
        if mode is None:
            mode = self.config.mode
        return mode
        
    def add_worker(self, name = None, 
                   update:bool= False,
                   fn = None,
                   mode:str=None,
                   in_queue:str=None,
                   out_queue:str=None,
                   verbose: bool = True):
        name = self.resolve_worker_name(name)
        mode = self.resolve_mode(mode)
        
        
        if name in self.workers and not update:
            return self.workers[name]
        
        queue_prefix = '::'.join(name.split('::')[:-1])
        kwargs = dict(
            in_queue = 'input' if in_queue is None else in_queue,
            out_queue = 'output' if out_queue is None else out_queue,   
            fn = self.default_fn if fn is None else fn,
        )

        self.add_queue(kwargs['in_queue'], mode=mode)
        self.add_queue(kwargs['out_queue'], mode=mode)
        
        if verbose:
            self.print(f"Adding worker: {name}, mode: {mode}, kwargs: {kwargs}")

        if self.config.mode == 'thread': 
        
            t = threading.Thread(target=self.forward_requests, kwargs=kwargs)
            worker = t
            self.workers[name] = t
            t.start()
        elif self.config.mode == 'process':
            p = multiprocessing.Process(target=self.forward_requests, kwargs=kwargs)
            self.workers[name] = t
            p.start()
     
        else:
            raise ValueError("Invalid mode. Must be 'thread' or 'process'.")
    
    # write tests
    @classmethod
    def test(cls, **kwargs):
        self  = cls(**kwargs)
        for i in range(10):
            self.add_request(f"Request {i+1}")  
        self.kill_workers()
    @classmethod
    def get_schema(cls, x):
        x = cls.munch2dict(x)
        if isinstance(x,dict):
            for k,v in x.items():
                if isinstance(v,dict):
                    x[k] = cls.get_schema(v)
                else:
                    x[k] = type(v)
        elif type(x) in [list, tuple, set]:
            x =  list(x)
            for i,v in enumerate(x):
                x[i] = cls.get_schema(v)
        else:
            x = type(x)
        
        return x
    
    cache = {}
    def background_fn(self, request, **kwargs):
        request_hash = 'BRO'
        c.print(f"Background worker: {request} {request_hash}")
    
    
    def default_fn(self,request, **kwargs):

        if isinstance(request, dict):
            # get request from queue
            # get function and arguments
            fn = request.get('fn', None) # identity function
            kwargs = request.get('kwargs', {})
            args = request.get('args', [])
            
            if not callable(fn):
                fn =lambda x: x
                
            assert callable(fn), f"Invalid function: {fn}"

            output = fn(*args, **kwargs)
            
            return output
        else:
            return None
            
    def forward_requests(self,  **kwargs):
        verbose = kwargs.get('verbose', True)
        in_queue = kwargs.get('in_queue', 'input')
        out_queue = kwargs.get('out_queue', 'output')
        fn = kwargs.get('fn', self.default_fn)
        name = kwargs.get('name', 'worker')
        worker_prefix = f"Worker::{name}"
        

        
        while True:
            request = self.queue[in_queue].get()
            if verbose:
                self.print(f"{worker_prefix} <-- request: {request}", color='yellow')
                
            if request == 'kill':
                if verbose: 
                    self.print(f"Killing worker: {name}", color='red')
                break
            
            
            output = fn(request, **kwargs)
            print(f"output: {output}")
            self.queue[out_queue].put(output)
            
            if verbose:
                self.print(f"{worker_prefix} --> result: {output}")
    def kill_loop(self):
        self.run_loop = False

    def kill_workers(self):
        # kill all workers
        for name, worker in self.workers.items():
            self.add_request('kill')
            self.queue.background.put('kill')
        for name, worker in self.workers.items():
            worker.join()
        
        
    def call(self,*args, fn=None, **kwargs):
        
        request = self.munch({'fn':fn, 'args': args, 'kwargs': kwargs})
        self.queue.input.put(request)

    
    add_request = call
        
    def __del__(self):
        self.kill()

if __name__ == "__main__":
    Pool.test()
    # Wait for all requests to be processed
    # queue.request_queue.join()

