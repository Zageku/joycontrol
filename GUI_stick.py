import tkinter as tk
from tkinter import Frame, Label, StringVar, ttk
import pyautogui
import socket
import os
import time
import math
from inputs import get_gamepad
import threading
import platform
try:
    os.system('xset r off')
except:
    pass
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.001
STICK_REVERSE_L = True    #切换左摇杆上下
STICK_REVERSE_R = True    #切换右摇杆上下
STICK_REVERSE_LX = False    #切换左摇杆左右
STICK_REVERSE_RX = False    #切换右摇杆左右

FILE_PATH = './traces'
key_map={
    'W':'up',
    'A':'left',
    'S':'down',
    'D':'right',
    'J':'y',
    'K':'b',
    'U':'x',
    'I':'a',
    'H':'l',
    'L':'r',
    'M':'minus',
    'N':'plus',
    'Q':'home',
    'E':'capture',
    'Y':'zl',
    'O':'zr',
    'SPACE':'b',
    'SHIFT_L':'zl',
    'R':'r_stick',
    'F':'l_stick',
    'Z':'record'    #录制操作
}

stick_map={
    'up':[0,2047],
    'down':[0,-2047],
    'left':[-2047,0],
    'right':[2047,0]
}
keys = key_map.values()
key_status = {}
for key in keys:
    key_status[key] = False


class sender:
    def __init__(self):
        self.S = socket.socket(type=socket.SOCK_DGRAM)
        self.S.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.record = False
        self.records = []
        self.last_time = 0
    
    def startREC(self):
        self.last_time = time.time()
        self.record = True
    
    def sendto(self,cmd,addr):
        self.S.sendto(cmd,addr)
        if self.record:
            self.records.append([time.time()-self.last_time,cmd.decode()])
            self.last_time += self.records[-1][0]
    def stopREC(self):
        '''录制操作保存'''
        t = time.localtime()
        self.record = False
        fname = f'{t.tm_year}{t.tm_mon}{t.tm_mday}{t.tm_hour}{t.tm_min}{t.tm_sec}.txt'
        content = ''
        for tr in self.records:
            content += f'%.3f {tr[1]}\n' % tr[0]    #精确到小数点后3位
        if len(content) > 0:
            with open(os.path.join(FILE_PATH,fname),'w') as f:
                f.write(content)
            self.records = []
        return content.count('\n')

S = sender()

class App(tk.Tk):
    btncfg = {
        'width':5,
        'foreground':'black',
        'highlightbackground':'green',
        'highlightthickness':3,
        #'background':'white',
        'borderwidth':2, 
        'relief':"solid" if int(platform.python_version_tuple()[1]) < 10 else 'flat'
    }
    btncfg_hold = {
        'foreground':'white',
        'highlightbackground':'white',
        'relief':'flat'
    }
    stickcfg = {
        'foreground':'cyan',
        'highlightbackground':'cyan',
        'relief':'flat'
    }
    def __init__(self,ip='10.15.0.38',port=20005):
        tk.Tk.__init__(self)
        self.title('点击空白捕获鼠标')
        self.x = 800
        self.y = 400
        self.geometry(f'+{self.x}+{self.y}')
        self.mouse_position_origin = [0,0]
        self.old_lstick = [0,0]
        self.lstick = [0,0]
        self.old_rstick = [0,0]
        self.rstick = [0,0]
        self.calibrate_delay = [0,4]
        self.delay_cnt = [0,0]
        self.mouse_mode = False
        self.mouse_cnt = 0
        self.mouse_history = [[0,0]]*3
        self.lstick_history = [[0,0]]*3
        self.ip = ip
        self.port = 20005
        self.addr = (ip,port)
        self.traces = []    #[['0.01', 'hold a'], ...]
        self.w = Frame(self)
        self.w.pack()
        self.tabControl = ttk.Notebook(self.w)
        self.tab1 = ttk.Frame(self.tabControl)
        self.tabControl.add(self.tab1,text='  主控  ')
        self.tab_1_build(self.tab1)
        self.tab2 = tk.LabelFrame(self.tabControl,text='Fn轨迹')
        self.tabControl.add(self.tab2,text='  宏键  ')
        self.tab_2_build(self.tab2)
        self.tabControl.pack()

    def tab_1_build(self,f):
        self.var1=tk.StringVar()
        self.var1.set(self.ip)
        self.e = ttk.Entry(f,textvariable=self.var1,width=26,state='disabled')
        self.e.grid(row=1,column=1,pady=5)
        self.REC_FLG = False
        def rec():
            if self.REC_FLG:
                length = S.stopREC()
                self.REC_btn.config(text='开始录制')
                S.sendto(b'record_stop',self.addr)
                self.title(f'录制完成({length})')
            else:
                self.REC_btn.config(text='停止录制')
                S.sendto(b'record_start',self.addr)
                S.startREC()
                self.title('录制中')
            self.REC_FLG = not self.REC_FLG
        self.rec = rec
        self.REC_btn = ttk.Button(f,text='开始录制',command=rec)
        self.REC_btn.grid(row=1,column=2,pady=5)

        self.bind('<KeyPress>',self.hold_key)
        self.bind('<KeyRelease>',self.release_key)
        self.e.bind('<Button-1>',lambda _: self.e.config(state='normal'))
        self.e.bind('<Return>',self.event_setaddr)
        self.e.bind("<FocusOut>", self.event_setaddr)
        def press_mouse_1(event):
            if self.mouse_mode:
                self.hold_key(key='zr')
        def release_mouse_1(event):
            if self.mouse_mode:
                self.release_key(key='zr')

        self.bind('<ButtonPress-1>',press_mouse_1)
        self.bind('<ButtonRelease-1>',release_mouse_1)
        self.bind('<ButtonPress-3>',lambda _:self.hold_key(key='r'))
        self.bind('<ButtonRelease-3>',lambda _:self.release_key(key='r'))

        self.wm_attributes('-topmost', 1)  # 锁定窗口置顶
        mainFrame = tk.Frame(f)
        mainFrame.grid(row=3,column=1,columnspan=2,padx=3,pady=3)
        #f.bind('<B1-Motion>',self.move)
        def release_mouse(e):
            self.mouse_mode = False
            self.title('点击空白捕获鼠标')
        def catch_mouse(e):
            if str(self.e.cget('state'))=='disabled':
                if not self.mouse_mode:
                    self.mouse_position_origin = pyautogui.position()
                    self.mouse_mode = True
                    self.title('按下ESC释放鼠标')
            else:
                self.event_setaddr()
                
        mainFrame.bind('<Button-1>',catch_mouse)
        self.bind('<Escape>',release_mouse)
        self.btnGUI = {}
        
        self.btnGUI['left'] = tk.Label(mainFrame,text='左',**self.btncfg)
        self.btnGUI['right'] = tk.Label(mainFrame,text='右',**self.btncfg)
        self.btnGUI['up'] = tk.Label(mainFrame,text='上',**self.btncfg)
        self.btnGUI['down'] = tk.Label(mainFrame,text='下',**self.btncfg)
        self.btnGUI['up'].grid(row=1,column=0,columnspan=2)
        self.btnGUI['left'].grid(row=2,column=0,columnspan=1)
        self.btnGUI['right'].grid(row=2,column=1,columnspan=1)
        self.btnGUI['down'].grid(row=3,column=0,columnspan=2)
        self.btnGUI['l'] = tk.Label(mainFrame,text='ZL',**self.btncfg)
        self.btnGUI['r'] = tk.Label(mainFrame,text='ZR',**self.btncfg)
        self.btnGUI['l'].grid(row=0,column=0,columnspan=1)
        self.btnGUI['r'].grid(row=0,column=5,columnspan=1)

        self.btnGUI['x'] = tk.Label(mainFrame,text='X',**self.btncfg)
        self.btnGUI['y'] = tk.Label(mainFrame,text='Y',**self.btncfg)
        self.btnGUI['a'] = tk.Label(mainFrame,text='A',**self.btncfg)
        self.btnGUI['b'] = tk.Label(mainFrame,text='B',**self.btncfg)
        self.btnGUI['y'].grid(row=2,column=4,columnspan=1)
        self.btnGUI['x'].grid(row=1,column=4,columnspan=2)
        self.btnGUI['a'].grid(row=2,column=5,columnspan=1)
        self.btnGUI['b'].grid(row=3,column=4,columnspan=2)

        self.btnGUI['plus'] = tk.Label(mainFrame,text='+',**self.btncfg)
        self.btnGUI['minus'] = tk.Label(mainFrame,text='-',**self.btncfg)
        self.btnGUI['home'] = tk.Label(mainFrame,text='H',**self.btncfg)
        self.btnGUI['plus'].grid(row=3,column=2,columnspan=1)
        self.btnGUI['minus'].grid(row=3,column=3,columnspan=1)
        self.btnGUI['home'].grid(row=2,column=2,columnspan=2)

        ttk.Separator(f,orient="horizontal").grid(row=4,column=1,columnspan=2,pady=1, sticky="we")
        self.cmdVar = tk.StringVar()
        self.cmdVar.set('下拉选择轨迹(.txt)文件')
        self.trSelector = ttk.Combobox(f,textvariable=self.cmdVar,width=24,state='readonly',name='')
        self.trSelector.bind("<<ComboboxSelected>>", self.readTr)
        self.trSelector.grid(row=5,column=1,pady=5)
        self.trSelector.bind('<Button-1>',self.getTrFiles)

        self.run_flgs = []
        self.runTr_BTN = ttk.Button(f,text='run',command=self.runTrace)
        self.runTr_BTN.grid(row=5,column=2,pady=5)
        self.after(1000,self.get_mouse_locate)
        t = threading.Thread(target=self.thread_gamepad)
        t.setDaemon(True)
        t.start()

    def tab_2_build(self,f):
        #以下数组索引0作为占位，不被使用
        self.tracesFn = ['']*13
        self.fnVars = [StringVar()]
        self.fnSelectors = [ttk.Combobox(f,textvariable=self.fnVars[-1],width=10,state='readonly')]
        self.fnLabels = [Label(f,text=f'F0')]
        self.runFlgsFn = [False]*13
        row_shift = 1
        column_shift =1
        for fn in range(1,13):
            #key_map['F'+str(fn)] = fn
            self.fnLabels.append(Label(f,text=f'F{fn}'))
            self.fnLabels[-1].grid(column=2*((fn-1)//6)+column_shift,row=(fn-1)%6+row_shift,pady=3)
            self.fnVars.append(StringVar())
            self.fnVars[-1].set('下拉选择文件')
            self.fnSelectors.append(ttk.Combobox(f,textvariable=self.fnVars[-1],width=13,state='readonly',name=str(fn)))
            self.fnSelectors[-1].bind("<<ComboboxSelected>>", lambda event:self.readTr(event,None,usefn=True))
            self.fnSelectors[-1].grid(column=2*((fn-1)//6)+1+column_shift,row=(fn-1)%6+row_shift)
            self.fnSelectors[-1].bind('<Button-1>',self.getTrFiles)


    def event_setaddr(self,event=None):
        try:
            self.e.config(state='disabled')
            ip = self.var1.get()
            if ip != '<broadcast>':
                socket.inet_pton(socket.AF_INET, ip)
            self.ip = ip
            self.addr = (ip,self.port)
        except:
            pass
    
    def getTrFiles(self,event=None):
        if os.path.exists(FILE_PATH):
            files = os.listdir(FILE_PATH)
            self.trSelector.config(values=files)
            for e in self.fnSelectors:
                e.config(values=files)
            return True
        else:
            os.mkdir(FILE_PATH)
            return True

    def readTr(self,event,tr_path=None,usefn=False):
        if tr_path is None:
            if usefn==False:fname = self.cmdVar.get()
            else:fn=int(event.widget.winfo_name());fname=self.fnVars[fn].get()
            tr_path = os.path.join(FILE_PATH,fname)
        with open(tr_path) as f:
            traces_with_comment = f.readlines()
        _traces = list(filter(lambda x: '#' not in x and len(x)>5, traces_with_comment))
        if usefn:
            self.tracesFn[fn] = [item.strip().split('#')[0].split(' ',maxsplit=1) for item in _traces]
        else:
            self.traces = [item.strip().split('#')[0].split(' ',maxsplit=1) for item in _traces]
        old_title = self.wm_title()
        if usefn:
            self.title(f'{len(self.tracesFn[fn])} 条记录被加载-F{int(event.widget.winfo_name())}')
            return self.tracesFn[fn]
        else:
            self.title(f'{len(self.traces)} 条记录被加载')
            return self.traces
    
    def runTrace(self,fn=0):
        '''当fn不为0时 表示执行/停止对应fn的轨迹
        fn为0时 执行/停止主控页轨迹
        '''
        def run(id_=-1):
            if fn==0:
                traces = self.traces
            else:
                traces = self.tracesFn[fn]
            time_absolute = 0
            traces_absolute = []
            old_title = self.wm_title()
            if fn==0:
                self.title(f'{len(traces)} 条记录执行中')
            else:
                self.title(f'{len(traces)} 条记录执行中-F{fn}')
            for time_stamp,cmd in traces:
                time_absolute = float(time_stamp)+time_absolute
                traces_absolute.append([time_absolute,cmd])
            start_time = time.time()
            
            for time_stamp,cmd in traces_absolute:
                time_delay = time_stamp - (time.time() - start_time)
                if time_delay > 0:
                    time.sleep(time_delay)
                if self.run_flgs[id_]:
                    break
                S.sendto(cmd.encode(),self.addr)
                
                #print(id_,fn,time_stamp,cmd)  #输出当前执行trace，会造成延迟
            
            #判断正常执行或中断
            if fn==0 and self.run_flgs[id_] != True:
                self.title(f'{len(traces)} 条执行完成')
                self.runTr_BTN.config(text='run')
                S.sendto(b'clear',self.addr)    #清空所有按键状态
            elif fn!=0 and self.run_flgs[id_] != True:
                self.title(f'{len(traces)} 条执行完成-F{fn}')
                self.fnLabels[fn].config(fg='SystemButtonText') #Fn指令不清空状态
            else:
                print(f'运行中断{id_}')
        self.title(f'JoyEMU')
        if fn==0:
            if self.runTr_BTN.cget('text')=='run':
                self.run_flgs.append(False)
                S.sendto(b'clear',self.addr)    #清空所有按键状态
                t = threading.Thread(target=run,args=[len(self.run_flgs)-1])
                t.setDaemon(True)
                t.start()
                self.runTr_BTN.config(text='stop')
            elif self.runTr_BTN.cget('text')=='stop':
                self.run_flgs[-1] = True
                S.sendto(b'clear',self.addr)    #清空所有按键状态
                self.runTr_BTN.config(text='run')
        else:
            #print(fn)
            if self.fnLabels[fn].cget('fg')=='SystemButtonText':
                self.run_flgs.append(False)
                self.runFlgsFn[fn] = len(self.run_flgs)-1
                t = threading.Thread(target=run,args=[len(self.run_flgs)-1])
                t.setDaemon(True)
                t.start()
                self.fnLabels[fn].config(fg='red')
            else:
                self.run_flgs[self.runFlgsFn[fn]] = True
                self.runFlgsFn[fn] = 0
                self.fnLabels[fn].config(fg='SystemButtonText')

    def get_mouse_locate(self):
        if not self.mouse_mode:
            self.after(100,self.get_mouse_locate)
        else:
            xy = pyautogui.position()
            dx = (xy[0] - self.mouse_position_origin[0])*50
            dy = -(xy[1] - self.mouse_position_origin[1])*50
            pyautogui.moveTo(self.mouse_position_origin)
            self.mouse_cnt += 1
            self.mouse_history.append([dx,dy])
            self.mouse_history.pop(0)
            dx_ = 0
            dy_ = 0
            for dx,dy in self.mouse_history:
                if abs(dx) > abs(dx_): dx_=dx
                if abs(dy) > abs(dy_): dy_=dy
            dx = dx_
            dy = dy_
            if dx > 2047: dx = 2047
            elif dx < -2047: dx = -2047
            if dy > 2047:dy = 2047
            elif dy < -2047: dy = -2047
            if self.old_lstick != [dx,dy] or self.old_lstick!=[0,0]:
                S.sendto(b'rstick '+str(dx).encode()+b' '+str(dy).encode(), self.addr)
                self.old_lstick = [dx,dy]
            #self.lstick_history.append(self.lstick.copy())
            #self.lstick_history.pop(0)
            self.after(16,self.get_mouse_locate)
            


    def btn_GUI_CFG(self,key,mode):
        #print(key,mode)
        if mode == 'hold':
            self.btnGUI[key.replace('z','').replace('_stick','')].config(**self.btncfg_hold)
        elif mode == 'release':
            self.btnGUI[key.replace('z','').replace('_stick','')].config(**self.btncfg)
        elif mode == 'stick':
            if key =='l_center_x':
                self.btnGUI['left'].config(**self.btncfg)
                self.btnGUI['right'].config(**self.btncfg)
            elif key == 'l_center_y':
                self.btnGUI['up'].config(**self.btncfg)
                self.btnGUI['down'].config(**self.btncfg)
            else:
                self.btnGUI[key.replace('z','').replace('_stick','')].config(**self.stickcfg)
    def hold_key(self,event=tk.Event(),key=None):
        global key_status
        if key is None:
            pressed = event.keysym.upper()
            #print(pressed)
            if pressed in ['F1','F2','F3','F4','F5','F6','F7','F8','F9','F10','F11','F12']:
                fn = int(pressed[1:])
                self.runTrace(fn)
                return True
            key = key_map.get(event.keysym.upper())
            if key=='record':
                self.rec()
                return True
        if key and not key_status[key]:
            key_status[key] = True
            if self.mouse_mode and key in ['left','right','up','down']:
                self.lstick[0] += stick_map[key][0]
                self.lstick[1] += stick_map[key][1]
                S.sendto(b'lstick '+str(self.lstick[0]).encode()+b' '+str(self.lstick[1]).encode(), self.addr)
                self.btn_GUI_CFG(key,'stick')
                return True
            else:
                if self.mouse_mode and key in ['zr','r'] and key_status['zr'] and key_status['r']:
                    key = 'r_stick' 
                    key_status[key] = True
                    S.sendto(b'hold '+key.encode(), self.addr)
                    self.btn_GUI_CFG(key,'stick')
                    return True
            S.sendto(b'hold '+key.encode(), self.addr)
            self.btn_GUI_CFG(key,'hold')
            return True

    def release_key(self,event=tk.Event(),key=None):
        global key_status
        if not key:
            key = key_map.get(event.keysym.upper())
        if key and key_status[key]:
            key_status[key] = False
            if self.mouse_mode and key in ['left','right','up','down']:
                self.lstick[0] -= stick_map[key][0]
                self.lstick[1] -= stick_map[key][1]
                S.sendto(b'lstick '+str(self.lstick[0]).encode()+b' '+str(self.lstick[1]).encode(), self.addr)
            else:
                if self.mouse_mode and key in ['zr','r'] and key_status['r_stick']:
                    key = 'r_stick'
                    key_status[key] = False
                S.sendto(b'release '+key.encode(), self.addr)
            self.btn_GUI_CFG(key,'release')
            return True

    def thread_gamepad(self):
        
        key = None
        code_map = {
            'ABS_Y':'lstick',
            'ABS_X':'lstick',
            'ABS_RY':'rstick',
            'ABS_RX':'rstick',
            'ABS_Z':'zl',
            'ABS_RZ':'zr',
            'BTN_TL':'l',
            'BTN_TR':'r',
            'BTN_SOUTH':'b',
            'BTN_NORTH':'y',
            'BTN_WEST':'x',
            'BTN_EAST':'a',
            'BTN_THUMBL':'l_stick',
            'BTN_THUMBR':'r_stick',
            'BTN_SELECT':'minus',
            'BTN_START':'plus',
            'ABS_HAT0X':['left','right'],
            'ABS_HAT0Y':['up','down'],
            'BTN_MODE':'home'
        }
        while True:
            try:
                events = get_gamepad()
            except:
                time.sleep(1)
                continue

            for event in events:
                key = code_map.get(event.code)
                key_ori = key   #将key原始值备份（在为摇杆时）
                if not key: continue
                state = event.state
                if isinstance(key,list):
                    if event.state==-1:key = key[0];state=1
                    elif event.state==1: key = key[1];state=1
                    else:
                        key = key[0] if key_status[key[0]] else key[1]
                        state = 0
                    
                if event.code == 'ABS_Y':
                    #print(state)
                    if STICK_REVERSE_L:
                        event.state = -event.state
                    if self.lstick[1] != int(-event.state / 16 -0.5):
                        self.lstick[1] = int(-event.state / 16 -0.5)
                        if self.lstick[1]< -200: key = 'down'
                        elif self.lstick[1] > 200: key = 'up'
                        else: key = 'l_center_y'
                    else: continue
                elif event.code == 'ABS_X':
                    if STICK_REVERSE_LX:
                        event.state = -event.state
                    if self.lstick[0] != int(event.state / 16 -0.5):
                        self.lstick[0] = int(event.state / 16 -0.5)
                        if self.lstick[0] < -200: key = 'left'
                        elif self.lstick[0] > 200: key = 'right'
                        else: key = 'l_center_x'
                    else: continue
                elif event.code == 'ABS_RY':
                    if STICK_REVERSE_R:
                        event.state = -event.state
                    if self.rstick[1] != int(-event.state / 16 -0.5):
                        self.rstick[1] = int(-event.state / 16 -0.5)
                    else: continue
                elif event.code == 'ABS_RX':
                    if STICK_REVERSE_RX:
                        event.state = -event.state
                    if self.rstick[0] != int(event.state / 16 -0.5):
                        self.rstick[0] = int(event.state / 16 -0.5)
                    else: continue
                else:
                    if isinstance(state,int): state = state>0
                    #print(key,key_status[key],state,(state==True))
                    if key_status[key]!= (state==True): #state由数字转换为布尔值，且按键状态与当前操作不同
                        key_status[key] = (state==True)
                        if state:S.sendto(b'hold '+key.encode(), self.addr);self.btn_GUI_CFG(key,'hold')#;print(b'hold '+key.encode())
                        else: S.sendto(b'release '+key.encode(), self.addr);self.btn_GUI_CFG(key,'release')#;print(b'release '+key.encode())
                        continue
                if key_ori == 'lstick':
                    S.sendto(key_ori.encode()+b' '+str(self.lstick[0]).encode()+b' '+str(self.lstick[1]).encode(), self.addr)
                    self.btn_GUI_CFG(key,'stick')
                    
                elif key_ori == 'rstick':
                    S.sendto(key_ori.encode()+b' '+str(self.rstick[0]).encode()+b' '+str(self.rstick[1]).encode(), self.addr)

def start_gui():
    a=App(ip='<broadcast>')
    a.mainloop() 

if __name__=='__main__':
    start_gui()
