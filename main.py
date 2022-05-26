from virtualMouse import VirtualMouse
from pynput.mouse import Button, Controller
from pynput import keyboard
import os

m1 = VirtualMouse()
keySender = Controller()
run = True


def on_press(key):
    try:
        #print('alphanumeric key {0} pressed'.format(key.char))
        if key.char == '1':  # toggles pauses the program
            m1.mouseRunning = not m1.mouseRunning
        elif key.char == '2':
            m1.drawLabels = not m1.drawLabels1
        elif key.char == '3':
            m1.drawConnections = not m1.drawConnections
        elif key.char == '4':
            m1.showHud = not m1.showHud
    except AttributeError:
        print('special key {0} pressed'.format(key))


def on_release(key):
    print('{0} released'.format(key))
    if key == keyboard.Key.esc:  # stops the program
        os._exit(0)


listener = keyboard.Listener(
    on_press=on_press,
    on_release=on_release)
listener.start()


def main():
    while True:
        m1.draw()


main()
