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
from pynput.keyboard import Key
from pynput.keyboard import Controller as kb
import win32api
import win32con


def avg(lst):  # finds average of a list
    if len(lst) > 0:
        return sum(lst) / len(lst)


class VirtualMouse:
    def __init__(self, acceleration=1.4, sens=1.5, moveThresh=0, frameSample=3, halfScreen=True):

        self.drawLabels = False  # draws id numbers of the hand landmarks
        self.drawConnections = True  # draws lines connecting hand landmarks
        self.showHud = True  # draws the Heads Up Display
        self.mouseRunning = True  # pauses mouse output response
        self.open = True  # run condition of the program

        self.acceleration = acceleration  # mouse acceleration
        self.sens = sens  # mouse x and y sensitivity
        # change sens to 1.5 for desk usage
        self.moveThresh = moveThresh  # threshold for mouse movement
        self.frameSample = frameSample
        self.halfScreen = halfScreen
        self.setBound()
        self.display = (1920, 1080)  # (1920,1080) resolution
        
        self.fingersRaised = [0, 0, 0, 0, 0]  # stores which fingers are raised
        self.prevfingersRaised = [self.fingersRaised * 3]

        self.pTime = 0  # stores time when last frame started
        # stores past 5 calculated frame times to average
        self.frameRate = [0 for i in range(5)]
        self.prevInput = (0, 0)

        self.keyboard = kb()

        ''' removed clicks
        self.clickThresh = 0.5
        self.lastClick = 0
        '''

        self.mouse = Controller()
        self.mouseCoords = (self.display[0]/2, self.display[1]/2)
        # stores mouse position of the past few frames
        self.lastPos = [(0, 0) for i in range(frameSample)]
        self.mouseAction = "None"
        self.leftDown = False
        self.rightDown = False
        self.midDown = False
        self.inBounds = False

        self.pinched = False
        self.pinchConditions = ()
        self.prevPinch = [False for i in range(frameSample)]

        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(False, 2, False, 0.5, 0.5)
        self.mpDraw = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)

    def setBound(self):
        if self.halfScreen:
            self.boundStart = (320, 40)  # (320,40) for halfscreen
            self.boundBox = (280, 350)  # (280,350) for halfscreen
        else:
            self.boundStart = (80, 40)
            self.boundBox = (520, 350)

    def avgPos(self, lst):  # finds average position of a matrix of x,y positions
        avgX = avg([x[0] for x in lst])
        avgY = avg([y[1] for y in lst])
        return [int(avgX), int(avgY)]

    def secant(self, x1, y1, x2, y2):  # finds secant of 2 x,y coordinates
        dy = y1-y2
        dx = x1-x2
        return dy/dx

    def dist(self, x1, y1, x2, y2):  # cartesian distance
        dx = x1 - x2
        dy = y1 - y2
        return (dx**2 + dy**2) ** 0.5

    def queue(self, lst, point):  # queue data structure
        newQueue = lst[1:]
        newQueue.append(point)
        return newQueue

    # checks if list of a target points is within 2 bounds
    def inRange(self, bound1, bound2, targets):
        inRange = False
        for target in targets:
            if bound1 < bound2 and target > bound1 and target < bound2:
                inRange = True
            elif bound2 < bound1 and target < bound1 and target > bound2:
                inRange = True
            else:
                return False
        return inRange

    # checks if movement is significant enough to not be noise
    def overThresh(self, startCoords, endCoords):
        if abs(startCoords[0] - endCoords[0]) > self.moveThresh or abs(startCoords[1] - endCoords[1]) > self.moveThresh:
            return True
        else:
            return False

    def signedExp(self, base, exp):  # exponentiation that preserves sign
        if base < 0:
            power = -(abs(base) ** exp)
        else:
            power = abs(base) ** exp
        return power

    def checkPinch(self, p1, p2, hand):  # checks for pinches
        # distance between knuckles to know scale of hand
        knuckleDist = self.dist(hand[5].x, hand[5].y, hand[1].x, hand[1].y)
        # changing distance threshold for pinch detection depending on hand size
        maxY = round(knuckleDist/4.5, 2)
        maxX = round(knuckleDist/8, 2)
        # prevents pinch detection while presenting closed fist
        if not self.inRange(hand[17].x, hand[3].x, [hand[4].x, hand[8].x]):
            dx = abs(p1[0] - p2[0])
            dy = abs(p1[1] - p2[1])
            #dz = abs(p1[2] - p2[2])
            self.pinchConditions = (dx < maxX, dy < maxY)  # , dz < 0.02)
            # print(maxY)
            #print("xyz Dist: ", round(dx,2), round(dy,2), round(dz,2))
            pinch = dx < maxX and dy < maxY  # and dz < 0.02
            self.prevPinch = self.queue(self.prevPinch, pinch)
            if self.prevPinch == [True for i in range(self.frameSample)]:
                self.pinched = True
            elif self.prevPinch == [False for i in range(self.frameSample)]:
                self.pinched = False
    # translates hand motion to mouse movements

    def mouseAcceleration(self, handLms, camSize, img):
        inputX = int(
            avg([handLms.landmark[item].x for item in [0, 9, 13]]) * camSize[0])  # x coord for center of palm
        inputY = int(
            avg([handLms.landmark[item].y for item in [0, 9, 13]]) * camSize[1])  # y coord for center of palm

        if (inputX > self.boundStart[0] and inputX < self.boundStart[0] + self.boundBox[0]  # checks if center of palm is within bounding box
                and inputY > self.boundStart[1] and inputY < self.boundStart[1] + self.boundBox[1]):
            self.inBounds = True
            moveX = self.signedExp(
                (inputX - self.prevInput[0]) * self.sens, self.acceleration)  # scales mouse movement with mouse sensitivity and acceleration
            moveY = self.signedExp(
                (inputY - self.prevInput[1]) * self.sens, self.acceleration)
            mouseX = self.mouseCoords[0] + moveX  # changes mouse coords
            mouseY = self.mouseCoords[1] + moveY
            '''
            if mouseX > self.display[0]:
                mouseX = self.display[0]
            if mouseX < 0:
                mouseX = 0
            if mouseY > self.display[1]:
                mouseY = self.display[1]
            if mouseY < 0:
                mouseY = 0
            '''
            self.mouseCoords = (round(mouseX), round(mouseY))
            self.lastPos = self.queue(self.lastPos, self.mouseCoords)
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
        cv2.circle(img, (inputX, inputY), 3, (255, 255, 0), - 1)

    def controlMouse(self):  # controls mouse functions
        if self.pinched:  # index and thumb pinched together
            if self.leftDown == False:
                self.leftDown = True
                self.mouse.press(Button.left)
                self.mouseAction = "Left"
        else:
            if self.leftDown == True:
                self.leftDown = False
                self.mouse.release(Button.left)
                self.mouseAction = "None"
        # if index and middle finger are raised
        if self.fingersRaised[1:5] == [1, 1, 0, 0]:
            if self.rightDown == False:
                self.rightDown = True
                self.mouse.press(Button.right)
                self.mouseAction = "Right"
        else:
            if self.rightDown == True:
                self.rightDown = False
                self.mouse.release(Button.right)
                self.mouseAction = "None"

        # index, middle and ring finger raised
        if self.fingersRaised[1:5] == [1, 1, 1, 0]:
            if self.midDown == False:
                '''
                if (time.time() - self.lastClick) > self.clickThresh:#
                    self.keyboard.press(Key.backspace)
                    self.keyboard.release(Key.backspace)
                    self.lastClick = time.time() #
                '''
                self.mouse.press(Button.middle)
                self.midDown = True
                self.mouseAction = "Mid"
        else:
            if self.midDown == True:
                self.mouse.release(Button.middle)
                self.midDown = False
                self.mouseAction = "None"
            '''
            if self.handY <= self.display[1] / 2:
                scroll = int((self.display[1]/2 - self.handY)/100)
            else:
                scroll = int(-(self.handY - self.display[1]/2)/100)
            self.mouse.scroll(0, scroll)
            '''
        # index and middle finger raised
        '''
        if self.leftDown == False and self.rightDown == False:
            if self.fingersRaised[1:3] == [1, 1]:
                if (time.time() - self.lastClick) > self.clickThresh:
                    self.mouse.click(Button.right, 1)
                    self.mouseAction = "Right Click"
                    self.lastClick = time.time()
            elif self.fingersRaised[1] == 1:  # index finger raised
                if (time.time() - self.lastClick) > self.clickThresh:
                    self.mouse.click(Button.left, 1)
                    self.mouseAction = "Left Click"
                    self.lastClick = time.time()
        '''

    def draw(self):  # draws camera and UI
        success, img = self.cap.read()  # tuple of boolean success and image feed
        img = cv2.flip(img, 1)  # inverts camera feed
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(imgRGB)
        h, w, c = img.shape

        y_offset = 5  # vertical position offset for number label on finger landmarks
        if results.multi_hand_landmarks:
            for handLms in results.multi_hand_landmarks:  # iterating through each hand
                if self.drawConnections:
                    self.mpDraw.draw_landmarks(
                        img, handLms, self.mpHands.HAND_CONNECTIONS)
                for id, lm in enumerate(handLms.landmark):
                    if self.drawLabels:
                        cv2.putText(img, str(id), (int(
                            lm.x * w), int(lm.y * h - y_offset)), cv2.FONT_HERSHEY_COMPLEX, 0.5, (0, 0, 255), 2)
                    if id % 4 == 0 and id > 4:
                        if (lm.y - handLms.landmark[id - 2].y) < 0:
                            self.fingersRaised[id // 4 - 1] = 1
                        else:
                            self.fingersRaised[id // 4 - 1] = 0
                indexCoords = [handLms.landmark[4].x,
                               handLms.landmark[4].y, handLms.landmark[4].z]
                thumbCoords = [handLms.landmark[8].x,
                               handLms.landmark[8].y, handLms.landmark[8].z]
                self.checkPinch(thumbCoords, indexCoords, handLms.landmark)

                if self.mouseRunning:
                    self.mouseAcceleration(handLms, (w, h), img)

                if self.inBounds and self.mouseRunning:
                    self.controlMouse()

        cTime = time.time()
        curFps = round(1/(cTime - self.pTime))
        self.frameRate = self.queue(self.frameRate, curFps)
        avgFps = "FPS: " + str(round(avg(self.frameRate)))
        self.pTime = cTime

        if self.showHud:
            cv2.putText(img, "Pinch:" + str(self.pinchConditions), (100, 20), cv2.FONT_HERSHEY_COMPLEX,
                        0.4, (0, 100, 0), 2)  # displays pinch x and y conditions
            cv2.putText(img, avgFps, (10, 20), cv2.FONT_HERSHEY_COMPLEX,
                        0.5, (0, 100, 0), 2)  # displays fps
            cv2.putText(img, "Action: " + self.mouseAction, (400, 15), cv2.FONT_HERSHEY_COMPLEX,
                        0.5, (0, 100, 0), 2)  # displays mouse action
            cv2.putText(img, "Fingers: " + str(self.fingersRaised), (400, 30),
                        cv2.FONT_HERSHEY_COMPLEX, 0.5, (0, 100, 0), 2)  # displays fingers raised
            cv2.putText(img, "[X,Y] " + str(self.mouse.position), (250, 20),
                        cv2.FONT_HERSHEY_COMPLEX, 0.4, (0, 100, 0), 2)  # displays fingers raised
        # draws virtual mousepad area
            cv2.rectangle(img, self.boundStart, (
                self.boundStart[0] + self.boundBox[0], self.boundStart[1] + self.boundBox[1]), (0, 0, 255), 2)
        cv2.imshow('Virtual Mouse', img)  # shows camera feed
        cv2.waitKey(1)  # waits for 1ms
