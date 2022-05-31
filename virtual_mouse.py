# Virtual Mouse
# Created by Sunny Yao
#
# Program designed to replace mouse control with a camera.
#
# Installation Setup
# Python 3.9+
# pip install cv2
# pip install mediapipe
# pip install pynput
# run main.py, not this file

import time
import cv2
import mediapipe as mp
from pynput.mouse import Button, Controller
#from pynput.keyboard import Key
#from pynput.keyboard import Controller as kb
import win32api
import win32con


def avg(lst):
    '''Returns average of a list.'''
    if len(lst) > 0:
        return sum(lst) / len(lst)


def queue(lst, point):
    '''Queue data structure.'''
    newQueue = lst[1:]
    newQueue.append(point)
    return newQueue


def dist(x1, y1, x2, y2):
    '''Finds Cartesian distance'''
    dx = x1 - x2
    dy = y1 - y2
    return (dx**2 + dy**2) ** 0.5


def inRange(bound1, bound2, targets):
    '''Checks if list of a target points is within 2 bounds.'''
    inRange = False
    for target in targets:
        if bound1 < bound2 and target > bound1 and target < bound2:
            inRange = True
        elif bound2 < bound1 and target < bound1 and target > bound2:
            inRange = True
        else:
            return False
    return inRange


def signedExp(base, exp):
    '''Exponentiation that preserves sign.'''
    if base < 0:
        power = -(abs(base) ** exp)
    else:
        power = abs(base) ** exp
    return power


# unused
def secant(x1, y1, x2, y2):
    '''finds secant of 2 x,y coordinates.'''
    dy = y1-y2
    dx = x1-x2
    return dy/dx


class VirtualMouse:
    def __init__(self, acceleration=1.1, sens=2, moveThresh=0, frameSample=3, halfScreen=False):
        '''UI'''
        self.drawLabels = False  # draws id numbers of the hand landmarks
        self.drawConnections = True  # draws lines connecting hand landmarks
        self.showHud = True  # draws the Heads Up Display
        self.mouseRunning = True  # pauses mouse output response
        self.open = True  # run condition of the program
        '''Mouse speed and Virtual Mousepad Settings'''
        self.acceleration = acceleration  # mouse acceleration
        self.sens = sens  # mouse x and y sensitivity
        self.moveThresh = moveThresh  # threshold for mouse movement
        self.frameSample = frameSample
        self.halfScreen = halfScreen
        self.setBound()
        self.display = (1920, 1080)  # (1920,1080) resolution

        '''Frame Rate'''
        self.pTime = 0  # stores time when last frame started
        # stores past 5 calculated frame times to average
        self.frameRate = [0 for i in range(5)]

        '''Mouse Controls'''
        #self.keyboard = kb()
        self.mouse = Controller()
        self.mouseCoords = self.mouse.position
        self.scrollThresh = 0.5
        self.lastScroll = 0
        # stores mouse position in previous frames
        self.lastPos = [(0, 0) for i in range(frameSample)]
        self.prevInput = ()
        self.fingersRaised = [0, 0, 0, 0, 0]  # stores which fingers are raised
        self.mouseAction = "None"
        self.leftDown = False
        self.rightDown = False
        self.midDown = False
        self.inBounds = False
        self.pinched = False
        self.pinchConditions = ()
        self.pinchSample = 3
        self.prevPinch = [False for i in range(
            self.pinchSample)]  # change to frameSample
        self.mouseOffset = False
        self.prevOffset = self.mouseOffset

        '''Camera feed processing'''
        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(False, 1, False, 0.5, 0.5)
        self.mpDraw = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)

        self.toggle = True

    def setBound(self):
        '''Sets virtual mousepad bounds'''
        if self.halfScreen:
            self.boundStart = (320, 40)
            self.boundBox = (280, 350)
        else:
            self.boundStart = (40, 40)
            self.boundBox = (560, 350)

    def avgPos(self, lst):
        '''Finds average position from a matrix of x,y positions and returns a tuple.'''
        avgX = avg([x[0] for x in lst])
        avgY = avg([y[1] for y in lst])
        return [int(avgX), int(avgY)]

    def checkPinch(self, p1, p2, hand):
        '''Checks for index and thumb pinches.'''
        # distance between knuckles to know scale of hand
        knuckleDist = dist(hand[5].x, hand[5].y, hand[1].x, hand[1].y)
        # changing distance threshold for pinch detection depending on hand size
        maxY = round(knuckleDist/4.5, 2)
        maxX = round(knuckleDist/8, 2)
        # prevents pinch detection while presenting closed fist
        if not inRange(hand[17].x, hand[3].x, [hand[4].x, hand[8].x]):
            dx = abs(p1[0] - p2[0])
            dy = abs(p1[1] - p2[1])
            self.pinchConditions = (dx < maxX, dy < maxY)
            pinch = dx < maxX and dy < maxY
            self.prevPinch = queue(self.prevPinch, pinch)
            # True * self.pinchSample
            if self.prevPinch == [True for i in range(self.pinchSample)]:
                self.pinched = True
            # False * self.pinchSample
            elif self.prevPinch == [False for i in range(self.pinchSample)]:
                self.pinched = False

    def mouseAcceleration(self, handLms, camSize, handFlip):
        '''Translates hand motion to mouse movements.'''
        inputX = int(
            avg([handLms.landmark[item].x for item in [0, 9, 13]]) * camSize[0])
        inputY = int(
            avg([handLms.landmark[item].y for item in [0, 9, 13]]) * camSize[1])
        if self.pinched:
            inputX = int(
                avg([handLms.landmark[item].x for item in [4, 8]]) * camSize[0])  # 4 is thumb, 8 is index
            inputY = int(
                avg([handLms.landmark[item].y for item in [4, 8]]) * camSize[1])
            self.mouseOffset = True
        else:
            self.mouseOffset = False
        if self.mouseOffset != self.prevOffset:
            self.prevInput = inputX, inputY
        self.prevOffset = self.mouseOffset

        xStart = self.boundStart[0]
        xEnd = self.boundStart[0] + self.boundBox[0]
        yStart = self.boundStart[1]
        yEnd = self.boundStart[1] + self.boundBox[1]
        # checks if center of palm is within bounding box
        if inRange(xStart, xEnd, [inputX]) and inRange(yStart, yEnd, [inputY]):
            self.inBounds = True
            if not self.prevInput:
                self.prevInput = inputX, inputY
            # scales mouse movement with mouse sensitivity and acceleration
            moveX = int(
                signedExp((inputX - self.prevInput[0]) * self.sens, self.acceleration))
            moveY = int(
                signedExp((inputY - self.prevInput[1]) * self.sens, self.acceleration) * handFlip)
            mouseX = self.mouseCoords[0] + moveX  # changes mouse coords
            mouseY = self.mouseCoords[1] + moveY
            self.mouseCoords = (mouseX, mouseY)
            self.lastPos = queue(self.lastPos, self.mouseCoords)
            avgPos = self.avgPos(self.lastPos)
            if self.fingersRaised[1:5] != [1, 1, 1, 1]:
                x = int(self.mouseCoords[0] - avgPos[0])
                y = int(self.mouseCoords[1] - avgPos[1])
                # necessary for centered mouse programs
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, x, y, 0, 0)
            self.prevInput = (inputX, inputY)
        else:
            self.inBounds = False
        # draws position of the center of the palm
        return inputX, inputY

    def controlMouse(self):
        '''Controls mouse button functions.'''
        if self.pinched:  # index and thumb pinched together
            if self.leftDown == False:
                self.leftDown = True
                self.mouse.press(Button.left)
                self.mouseAction = "Left"
        elif self.leftDown == True:
            self.leftDown = False
            self.mouse.release(Button.left)
            self.mouseAction = "None"
        # Index and middle finger are raised
        elif self.fingersRaised[1:5] == [1, 1, 0, 0]:
            if self.rightDown == False:
                self.rightDown = True
                self.mouse.press(Button.right)
                self.mouseAction = "Right"
        elif self.rightDown == True:
            self.rightDown = False
            self.mouse.release(Button.right)
            self.mouseAction = "None"
        # Index, middle and ring finger raised
        elif self.fingersRaised[1:5] == [1, 1, 1, 0]:
            if self.midDown == False:
                self.mouse.press(Button.middle)
                self.midDown = True
                self.mouseAction = "Mid"
                '''
                if (time.time() - self.lastClick) > self.clickThresh:#
                    self.keyboard.press(Key.backspace)
                    self.keyboard.release(Key.backspace)
                    self.lastClick = time.time() #
                '''
            '''
            if self.mouse.position[1] <= self.display[1] / 2:
                scroll = int((self.display[1]/2 - self.mouse.position[1])/200)
            else:
                scroll = int(-(self.mouse.position[1] - self.display[1])/200)
            print("scroll: ", scroll)
            if (time.time() - self.lastScroll) > self.scrollThresh:#
                scroll = 1
                self.mouse.scroll(0, scroll)
                self.lastScroll = time.time()
                '''
        elif self.midDown == True:
            self.mouse.release(Button.middle)
            self.midDown = False
            self.mouseAction = "None"

    def draw(self):
        '''Draws camera feed and UI'''
        success, img = self.cap.read()  # tuple of boolean success and image feed
        img = cv2.flip(img, 1)  # inverts camera feed for front facing camera
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)# Converts BGR image to RGB
        results = self.hands.process(imgRGB)
        

        h, w, c = img.shape
        y_offset = 5  # vertical position offset for number label on finger landmarks
        if results.multi_hand_landmarks:
            if self.toggle:
                print(results.multi_hand_landmarks)
                self.toggle = False
            for handLms in results.multi_hand_landmarks:  # iterating through each hand
                if self.drawConnections:
                    self.mpDraw.draw_landmarks(
                        img, handLms, self.mpHands.HAND_CONNECTIONS)
                handFlip = - \
                    1 if handLms.landmark[0].y < handLms.landmark[9].y else 1
                for id, lm in enumerate(handLms.landmark):
                    if self.drawLabels:
                        cv2.putText(img, str(id), (int(
                            lm.x * w), int(lm.y * h - y_offset)), cv2.FONT_HERSHEY_COMPLEX, 0.5, (0, 0, 255), 2)
                    if id % 4 == 0 and id > 4:
                        if (lm.y - handLms.landmark[id - 2].y) * handFlip < 0:
                            self.fingersRaised[id // 4 - 1] = 1
                        else:
                            self.fingersRaised[id // 4 - 1] = 0
                    elif id == 4:
                        if (lm.x - handLms.landmark[3].x) < 0 and (lm.y - handLms.landmark[3].y)*handFlip < 0:
                            self.fingersRaised[0] = 1
                        else:
                            self.fingersRaised[0] = 0
                indexCoords = [handLms.landmark[4].x,
                               handLms.landmark[4].y, handLms.landmark[4].z]
                thumbCoords = [handLms.landmark[8].x,
                               handLms.landmark[8].y, handLms.landmark[8].z]
                self.checkPinch(thumbCoords, indexCoords, handLms.landmark)
                if self.mouseRunning:
                    cv2.circle(img, self.mouseAcceleration(
                        handLms, (w, h), handFlip), 3, (255, 255, 0), - 1)
                    if self.inBounds:
                        self.controlMouse()
        cTime = time.time()
        curFps = round(1/(cTime - self.pTime))
        self.frameRate = queue(self.frameRate, curFps)
        avgFps = round(avg(self.frameRate))
        self.pTime = cTime

        color = (255, 255, 255)
        size = 0.5
        if self.showHud:
            cv2.putText(img, "FPS: " + str(avgFps), (10, 20), cv2.FONT_HERSHEY_SIMPLEX,
                        size, color, 2)  # displays fps
            cv2.putText(img, "Pinch:" + str(self.pinchConditions), (80, 20), cv2.FONT_HERSHEY_SIMPLEX,
                        size, color, 2)  # displays pinch x and y conditions
            cv2.putText(img, "[X,Y] " + str(self.mouse.position), (250, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, size, color, 2)  # displays mouse position
            cv2.putText(img, "Action: " + self.mouseAction, (400, 15), cv2.FONT_HERSHEY_SIMPLEX,
                        size, color, 2)  # displays mouse action
            cv2.putText(img, "Fingers: " + str(self.fingersRaised), (400, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, size, color, 2)  # displays fingers raised
            cv2.rectangle(img, self.boundStart, (
                self.boundStart[0] + self.boundBox[0], self.boundStart[1] + self.boundBox[1]), (0, 0, 255), 1)  # draws virtual mousepad area

        cv2.imshow('Virtual Mouse', img)  # shows camera feed
        cv2.waitKey(1)  # waits for 1ms
