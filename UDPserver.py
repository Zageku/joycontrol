import socket
import asyncio
import threading
import time

class Server(object):
    def __init__(self,func=[],port=20005):
        self.hold, self.release, self.available_buttons, self.lstick, self.rstick = func
        S = socket.socket(type=socket.SOCK_DGRAM)
        S.setblocking(False)
        S.bind(('0.0.0.0',port))
        self.S = S
        self.start()
    
    def start(self):
        def _start():
            loop = asyncio.new_event_loop()
            while True:
                try:
                    res,_ = self.S.recvfrom(1500)
                    #print(res,_)
                    cmd,*arg = res.decode().split(' ')
                    if cmd == 'hold':
                        self.hold(*arg)
                    elif cmd == 'release':
                        self.release(*arg)
                    elif cmd == 'lstick':
                        print('l')
                        dx = int(arg[0])
                        dy = int(arg[1])
                        self.lstick.set_h(dx+2048)
                        self.lstick.set_v(dy+2048)
                    elif cmd == 'rstick':
                        dx = int(arg[0])
                        dy = int(arg[1])
                        print('r')
                        self.rstick.set_h(dx+2048)
                        self.rstick.set_v(dy+2048)
                except:
                    pass
        async def async_start():
            record_flag = False
            rec = ''
            old_t = 0
            while True:
                try:
                    res = await loop.sock_recv(self.S,1500)
                    try:
                        cmd,*arg = res.decode().split(' ')
                        if cmd == 'hold':
                            self.hold(*arg)
                        elif cmd == 'release':
                            self.release(*arg)
                        elif cmd == 'lstick':
                            dx = int(arg[0])
                            dy = int(arg[1])
                            self.lstick.set_h(dx+2048)
                            self.lstick.set_v(dy+2048)
                        elif cmd == 'rstick':
                            dx = int(arg[0])
                            dy = int(arg[1])
                            self.rstick.set_h(dx+2048)
                            self.rstick.set_v(dy+2048)
                        elif cmd == 'record_start':
                            print('Recording...')
                            record_flag = True
                            rec = ''
                            if arg:
                                fname = arg[0]
                            else:
                                fname = time.asctime().replace(':','').replace(' ','')
                            old_t = time.time()
                            continue
                        elif cmd == 'record_stop':
                            record_flag = False
                            if len(rec)>0:
                                with open(fname,'w') as f:
                                    f.write(rec) 
                                print(f'Trace file {fname} saved...')
                            continue
                        elif cmd == 'clear':
                            for btn in self.available_buttons:
                                self.release(btn)
                        if record_flag:
                            t = time.time()
                            rec += f'{t-old_t} {cmd} {arg[0]}\n'
                            old_t = t
                    except:
                        print('[UDP ERROR]',cmd,arg)
                        pass
                except:
                    print('UDP server occured an error...')
                    self.S.close()
                    break
        loop = asyncio.get_running_loop()
        loop.create_task(async_start())
        '''
        t = threading.Thread(target=_start)
        t.setDaemon(True)
        t.start()'''
    
    def update(self,func=[]):
        self.hold, self.release, self.send = func
        print('SERVER COMMAND updated.')

if __name__=='__main__':
    def func2(arg):
        print(arg)
    async def func1(arg):
        print(arg)
    func = [func2,func2,func1,None,None]
    s = Server(func)
    #s.start()
    loop = asyncio.get_event_loop()
    loop.run_forever()
    while True:
        time.sleep(20)
        loop.call_soon(loop.stop())