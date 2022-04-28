from hand import Hand
from pynput.mouse import Button, Controller
from pynput import keyboard
import os

hand1 = Hand(moveThresh = 10, frameSample = 10)
keySender = Controller()

def on_press(key):
    try:
        #print('alphanumeric key {0} pressed'.format(key.char))
        if key.char == '/': #toggles pauses the program
            hand1.running = not hand1.running
    except AttributeError:
        print('special key {0} pressed'.format(key))

def on_release(key):
    #print('{0} released'.format(key))
    if key == keyboard.Key.esc: #stops the program
        os._exit(0) 

listener = keyboard.Listener(
    on_press=on_press,
    on_release=on_release)
listener.start()

def main():
    while True:
        if hand1.running:
            hand1.draw()

main()