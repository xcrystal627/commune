
import commune as c
import os
import pandas as pd
from typing import *

class Vali(c.Module):
    endpoints = ['score', 'scoreboard']
    epoch_time = 0
    vote_time = 0 # the time of the last vote (for voting networks)
    epochs = 0 # the number of epochs
    def __init__(self,
                    network= 'local', # for local subspace:test or test # for testnet subspace:main or main # for mainnet
                    search : Optional[str] =  None, # (OPTIONAL) the search string for the network 
                    batch_size : int = 128, # the batch size of the most parallel tasks
                    score : Union['callable', int]= None, # score function
                    key : str = None,
                    tempo : int = 60 , 
                    timeout : int = 3, # timeout per evaluation of the module
                    update : bool =False, # update during the first epoch
                    run_loop : bool = True, # This is the key that we need to change to false
                    path : str= None, # the storage path for the module eval, if not null then the module eval is stored in this directory
                 **kwargs):     
        self.timeout = timeout
        self.batch_size = batch_size
        self.set_key(key)
        self.sync_network(network=network, 
                          tempo=tempo, 
                          search=search, 
                          path=path, 
                          update=update)
        self.set_score(score)
        c.thread(self.run_loop) if run_loop else ''
    init_vali = __init__

    def set_score(self, score=None):
        if score == None:
            score = self.score
        if isinstance(score, str):
            score = c.get_fn(score)
        if callable(score):
            setattr(self, 'score', score )
        c.print(f'Score({self.score})')
        assert callable(self.score), f'SCORE NOT SET {self.score}'
        return {'success': True, 'msg': 'Score function set'}
    
    def set_key(self, key):
        self.key = c.get_key(key or self.module_name())
        return {'success': True, 'msg': 'Key set', 'key': self.key}

    def sync_network(self, network:str = None, 
                    subnet:str=None, 
                    tempo:int=60, 
                    search:str=None, 
                    path:str=None, 
                     update = False):
        self.network = network or 'server'
        self.subnet = subnet or 0
        if '/' in self.network:
            self.network, self.subnet = self.network.split('/')
        self.network_module = c.module(self.network)() 
        self.tempo = tempo or 60
        self.search = search or None
        self.path = os.path.abspath(path or self.resolve_path(f'{network}/{subnet}' if subnet else network))
        self.modules = self.network_module.modules(subnet=self.subnet, max_age=self.tempo, update=update)
        self.params = self.network_module.params(subnet=self.subnet, max_age=self.tempo, update=update)
        self.modules = [m for m in self.modules if self.search in m['name']] if self.search else self.modules
        self.n  = len(self.modules)  
        self.network_info = {'n': self.n, 'network': self.network  ,  'subnet': self.subnet, 'params': self.params}
        c.print(f'Network({self.network_info})')
        return self.network_info
    
    def score(self, module):
        info = module.info()
        return int('name' in info)
    
    def set_score(self, score):
        if callable(score):
            setattr(self, 'score', score )
        assert callable(self.score), f'SCORE NOT SET {self.score}'
        return {'success': True, 'msg': 'Score function set'}

    def run_loop(self):
        while True:
            try:
                self.epoch()
            except Exception as e:
                c.print('XXXXXXXXXX EPOCH ERROR ----> XXXXXXXXXX ',c.detailed_error(e), color='red')
    @property
    def time_until_next_epoch(self):
        return int(self.epoch_time + self.tempo - c.time())

    def get_client(self, module:dict) -> 'commune.Client':
        if not hasattr(self, '_clients'):
            self._clients = {}
        feature2type = {'name': str, 'url': str, 'key': str}
        for f, t in feature2type.items():
            assert f in module, f'Module missing {f}'
            assert isinstance(module[f], t), f'Module {f} is not {t}'
        if isinstance(module, str):
            module = self.network_module.get_module(module)
        if module['key'] in self._clients:
            client =  self._clients[module['key']]
        else:
            if isinstance(module, str):
                url = module
            else:
                url = module['url']
            client =  c.client(url, key=self.key)
            self._clients[module['key']] = client
        return client

    def score_module(self,  module:dict, **kwargs):
        client = self.get_client(module) # the client
        t0 = c.time() # the timestamp
        try:
            score = self.score(client, **kwargs)
        except Exception as e:
            score = 0
            module['error'] = c.detailed_error(e)
        module['score'] = score
        module['time'] = t0
        module['latency'] = c.time() - module['time']
        module['path'] = self.path +'/'+ module['key'] + '.json'
        return module

    def score_batch(self, modules: List[dict]):
        try:
            results = []
            futures = [c.submit(self.score_module, [m], timeout=self.timeout) for m in modules]   
            for f in c.as_completed(futures, timeout=self.timeout):
                m = f.result()
                print(m)
                if m.get('score', 0) > 0:
                    c.put_json(m['path'], m)
                    results.append(m)
        except Exception as e:
            c.print(f'ERROR({c.detailed_error(e)})', color='red')
        return results

    def epoch(self):
        next_epoch = self.time_until_next_epoch
        self.sync_network()
        c.print(f'Epoch(network={self.network} epoch={self.epochs} n={self.n})', color='yellow')
        batches = [self.modules[i:i+self.batch_size] for i in range(0, self.n, self.batch_size)]
        progress = c.tqdm(total=len(batches), desc='Evaluating Modules')
        results = []
        n_batches = len(batches)
        for i, batch in enumerate(batches):
            c.print(f'Batch(i={i}/{n_batches})', color='yellow')
            results += self.score_batch(batch)
            progress.update(1)
        self.epochs += 1
        self.epoch_time = c.time()
        self.vote(results)
        return results
    
    @property
    def votes_path(self):
        return self.path + f'/votes'

    def vote(self, results):
        voting_network = bool(hasattr(self.network_module, 'vote'))
        if not voting_network :
            return {'success': False, 'msg': f'NOT VOTING NETWORK({self.network})'}
        vote_staleness = c.time() - self.vote_time
        if vote_staleness < self.tempo:
            return {'success': False, 'msg': f'Vote is too soon {vote_staleness}'}
        if len(results) == 0:
            return {'success': False, 'msg': 'No results to vote on'}
        params = dict(modules=[], weights=[],  key=self.key, subnet=self.subnet)
        for m in results:
            if not isinstance(m, dict) or 'key' not in m:
                continue
            params['modules'].append(m['key'])
            params['weights'].append(m['score'])
        return self.network_module.vote(**params)
    
    def scoreboard(self,
                    keys = ['name', 'score', 'latency',  'url', 'key'],
                    ascending = True,
                    by = 'score',
                    to_dict = False,
                    page = None,
                    **kwargs
                    ):
        page_size = 1000
        max_age = self.tempo
        df = []
        # chunk the jobs into batches
        for path in self.module_paths():
            r = self.get(path, {},  max_age=max_age)
            if isinstance(r, dict) and 'key' and  r.get('score', 0) > 0  :
                df += [{k: r.get(k, None) for k in keys}]
            else :
                self.rm(path)
        df = c.df(df) 
        if len(df) > 0:
            if isinstance(by, str):
                by = [by]
            df = df.sort_values(by=by, ascending=ascending)
        if to_dict:
            return df.to_dict(orient='records')
        if len(df) > page_size:
            pages = len(df)//page_size
            page = page or 0
            df = df[page*page_size:(page+1)*page_size]
        return df


    def module_paths(self):
        return c.ls(self.path) # fam
    
    @classmethod
    def run_epoch(cls, network='local', run_loop=False, update=False, **kwargs):
        return  cls(network=network, run_loop=run_loop, update=update, **kwargs).epoch()
    
    def refresh_scoreboard(self):
        path = self.path
        c.rm(path)
        return {'success': True, 'msg': 'Leaderboard removed', 'path': path}

    


    def test(  
                n=2, 
                tag = 'vali_test_net',  
                miner='module', 
                trials = 5,
                tempo = 4,
                update=True,
                path = '/tmp/commune/vali_test',
                network='local'
                ):
            Vali  = c.module('vali')
            test_miners = [f'{miner}::{tag}{i}' for i in range(n)]
            modules = test_miners
            search = tag
            assert len(modules) == n, f'Number of miners not equal to n {len(modules)} != {n}'
            for m in modules:
                c.serve(m)
            namespace = c.namespace()
            for m in modules:
                assert m in namespace, f'Miner not in namespace {m}'
            vali = Vali(network=network, search=search, path=path, update=update, tempo=tempo, run_loop=False)
            print(vali.modules)
            scoreboard = []
            while len(scoreboard) < n:
                c.sleep(1)
                scoreboard = vali.epoch()
                trials -= 1
                assert trials > 0, f'Trials exhausted {trials}'
            for miner in modules:
                c.print(c.kill(miner))
            return {'success': True, 'msg': 'subnet test passed'}

        


        
