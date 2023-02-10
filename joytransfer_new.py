
import os
import time
import argparse
import asyncio
import logging

from multiprocessing import Process
from multiprocessing import Queue

from joycontrol.controller import Controller
from joycontrol.memory import FlashMemory
import joycontrol.report as report
from patch_joycontrol.protocol import controller_protocol_factory
from patch_joycontrol import protocol 
from patch_joycontrol.server import create_hid_server
import readline

import signal
import shlex
from UDPserver import Server
def _exit(signum, frame):
    '''连续两次ctrl+c退出程序'''
    global STOP_FLAG,STOP_FLAG_
    if STOP_FLAG and not STOP_FLAG_:
        print('按下回车退出')
        STOP_FLAG_ = True
        exit()
    elif not STOP_FLAG and not STOP_FLAG_:
        STOP_FLAG = True
        print('连续两次ctrl+c退出程序')
signal.signal(signal.SIGINT, _exit)
signal.signal(signal.SIGTERM, _exit)

protocol.SHOWFRAME_TIME = False #设置为True以显示6000帧数据包所用的时间
SHOW_TRACE_CMDS = False #为True会在trace指令中显示当前操作

NS_MAC = None
udpServer = None
STOP_FLAG = False
STOP_FLAG_ = False

HELP = '''
    当出现 >> 时连接完成，可执行指令
    1、按键     a、b、left、plus 等
                使用 && 同时操作多个按键，如 zr&&zl
    2、trace [file]   轨迹操作
                使用 trace filename 进行轨迹操作
    3、lstick/rstick [x_value,y_value]   摇杆操作
                其中参数值为0～4095
                lstick 2048 2048标示左摇杆归位
                rstick 0 2048表示右摇杆完全向左
    4、exit 退出帮助
    连续按两次Ctrl+C退出程序（以及1次回车）

    UDP服务器（20005端口）用来远程操作数据，支持记录、摇杆、按键操作

'''

async def execute_tr2(ctrl,file):
    '''传入控制器和文件名，执行文件轨迹操作
    '''
    def readTr(file='./traces.tr'):
        with open(file) as f:
            traces_with_comment = f.readlines()
        _traces = list(filter(lambda x: '#' not in x and len(x)>5, traces_with_comment))
        _traces = [item.strip().split(' ',maxsplit=1) for item in _traces]
        traces = [[float(item[0]),item[1]] for item in _traces]
        for tr in traces:
            if 'hold' not in tr[1] and 'release' not in tr[1]:
                print('File error\n  ',tr)
                return []
        print(f'{len(traces)} traces loaded...')
        return traces
    def checkTrace(traces):
        nonlocal buttons
        flg = True
        for tr in traces:
            if len(tr) != 3: 
                print(f'trace {tr} error [item nums]'); flg = False
            elif tr[-1] not in buttons:
                print(f'trace {tr} error [button]'); flg = False
            elif tr[1] not in ['hold','release']:
                print(f'trace {tr} error [cmd]'); flg = False
        return flg
    # Use Absolute time
    global STOP_FLAG
    buttons = ctrl.button_state.get_available_buttons()
    try:
        traces = readTr(file)
    except:
        print('file error')
        return False
    
    index = 0   # Fix time stamp to absolute time.将文件的相对时间转为绝对时间
    for i in range(1,len(traces)):
        traces[i][0] = traces[i-1][0] + traces[i][0]
    traces = [(item[0],*item[1].split(' ')) for item in traces]
    trace_len = len(traces)
    if not checkTrace(traces):
        return False
    print(trace_len)
    await loop.run_in_executor(None,input,'Press Enter to start >> ')
    t = time.time()
    while index < trace_len-2:
        dt = t+traces[index][0]-time.time()
        await asyncio.sleep(dt)
        user_input = traces[index][1:]      
        index += 1
        if user_input[0] == 'hold':
            ctrl.button_state.set_button(user_input[1], pushed=True)
        else:
            ctrl.button_state.set_button(user_input[1], pushed=False)
        if STOP_FLAG:
            print('Trace stop.')
            ctrl.button_state.set_button('plus', pushed=True)
            await asyncio.sleep(0.1)
            ctrl.button_state.set_button('plus', pushed=False)
            break
        if SHOW_TRACE_CMDS:
            print(f'{index} '+ '%.4f' % traces[index][0] +f' {traces[index][1:]}\n')
    for button in buttons:
        ctrl.button_state.set_button(button, pushed=False)


async def test_button(ctrl, *btns):
        available_buttons = ctrl.button_state.get_available_buttons()
        for btn in btns:
            if btn == 'wake':
                # wake up control
                ctrl.button_state.clear()
                #await ctrl.send()
                await asyncio.sleep(0.050) # stable minimum 0.050

            if btn not in available_buttons:
                return 1

        for btn in btns:
            ctrl.button_state.set_button(btn, pushed=True)  #hold
        #await ctrl.send()

        await asyncio.sleep(0.050) # stable minimum 0.050 press
        for btn in btns:
            ctrl.button_state.set_button(btn, pushed=False) #release
        #await ctrl.send()
        await asyncio.sleep(0.020) # stable minimum 0.020 release

        return 0

async def _main(args):

    # Get controller name to emulate from arguments
    controller = Controller.PRO_CONTROLLER
    global NS_MAC
    if NS_MAC is not None:
        reconnect_bt_addr = NS_MAC
    else:
        reconnect_bt_addr = args.reconnect_bt_addr
    # prepare the the emulated controller
    spi_flash = FlashMemory()
    factory = controller_protocol_factory(controller,spi_flash=spi_flash,
                            reconnect = reconnect_bt_addr)

    ctl_psm, itr_psm = 17, 19

    print('  Joy Transfer  v0.1')
    print('INFO: Waiting for Switch to connect...')


    transport, protocol, ns_addr = await create_hid_server(factory,
                                                  reconnect_bt_addr=reconnect_bt_addr,
                                                  ctl_psm=ctl_psm,
                                                  itr_psm=itr_psm,
                                                  unpair = not reconnect_bt_addr)
    controller_state = protocol.get_controller_state()
    if ns_addr is not None:
        NS_MAC = ns_addr
        # this is needed

        await controller_state.connect()
    print('[Switch MAC Address]: ',NS_MAC)

    if not reconnect_bt_addr:
        reconnect_bt_addr = ns_addr

    
    
    global STOP_FLAG
    available_buttons = controller_state.button_state.get_available_buttons()
    lstick = controller_state.l_stick_state
    rstick = controller_state.r_stick_state
    CMDS = [lambda x: controller_state.button_state.set_button(x, pushed=True), 
            lambda x: controller_state.button_state.set_button(x, pushed=False),
            available_buttons,
            controller_state.l_stick_state,
            controller_state.r_stick_state]
    global udpServer
    if not udpServer:
        udpServer = Server(func=CMDS)   #  start UDP input server
    else:
        udpServer = Server(func=CMDS)

    print('hi :3')
    #loop.create_task(sender(100,controller_state._protocol.send_controller_state))
    while True:
        try:
            user_input = await loop.run_in_executor(None,input,'>> ')
            STOP_FLAG = False
            if not user_input:
                continue

            buttons_to_push = []
            for command in user_input.split('&&'):
                cmd, *args = shlex.split(command)
                cmd = cmd.lower()
                if cmd == 'trace':
                    await execute_tr2(controller_state,args[0])
                elif cmd == 'lstick':
                    lstick.set_h(int(args[0]))
                    lstick.set_v(int(args[1]))
                elif cmd == 'rstick':
                    rstick.set_h(int(args[0]))
                    rstick.set_v(int(args[1]))
                elif cmd in available_buttons:
                    buttons_to_push.append(cmd)
                elif cmd == 'exit':
                    print('连续按下ctrl+c完成退出')
                elif cmd == 'help':
                    print(HELP)
                elif cmd == '6axis':
                    report._6axis[int(args[0])] = int(args[1])
                else:
                    print('command', cmd, 'not found, call help for help.')

            if buttons_to_push:
                await test_button(controller_state, *buttons_to_push)
            else:
                pass
        except:
            break

def handle_exception(loop, context):
    tasks = [t for t in asyncio.all_tasks() if t is not
                         asyncio.current_task()]
    for task in tasks:
        task.cancel()


if __name__ == '__main__':

    # check if root
    if not os.geteuid() == 0:
        raise PermissionError('Script must be run as root!')

    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--reconnect_bt_addr', type=str, default=None,
                        help='The Switch console Bluetooth address (or "auto" for automatic detection), for reconnecting as an already paired controller.')

    parser.add_argument('--nfc', type=str, default=None)
    args = parser.parse_args()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handle_exception)
    
    while True:
        loop.run_until_complete(
            _main(args)
        )

