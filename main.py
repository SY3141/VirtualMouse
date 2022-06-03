# Virtual Mouse
# Created by Sunny Yao
#
# Program designed to replace mouse control with a camera.
#
# Installation Setup in README.md

from virtual_mouse import VirtualMouse
from pynput import keyboard

m1 = VirtualMouse()


def on_press(key): 
    try:
        #print('alphanumeric key {0} pressed'.format(key.char))
        if key.char == '1':  # toggles pauses the program
            m1.mouseRunning = not m1.mouseRunning
        elif key.char == '2':
            m1.drawLabels = not m1.drawLabels
        elif key.char == '3':
            m1.drawConnections = not m1.drawConnections
        elif key.char == '4':
            m1.halfScreen = not m1.halfScreen
            m1.setBound()
        elif key.char == '5':
            m1.showHud = not m1.showHud
    except AttributeError:
        print('special key {0} pressed'.format(key))


def on_release(key):
    print('{0} released'.format(key))
    if key == keyboard.Key.esc:  # stops the program
        m1.open = False


listener = keyboard.Listener(
    on_press=on_press,
    on_release=on_release)
listener.start()

def main():
    while m1.open:
        m1.draw()

main()