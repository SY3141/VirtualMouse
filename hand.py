import time
import cv2
import mediapipe as mp
from pynput.mouse import Button, Controller

class Hand:
    def __init__(self,drawHand = False, moveThresh = 20, suppressShake = True, frameSample = 5):
        self.drawHand = drawHand #boolean: draws connections of the hand landmarks
        self.moveThresh = moveThresh
        self.suppressShake = suppressShake

        self.mouseDown = False
        self.finger_dist = 40
        self.pTime = 0 
        self.display = (1920,1080) #(1920,1080) self.display
        self.finger_dist = 40
        self.pTime = 0 
        self.prevX = 0
        self.prevY = 0
        self.tipIds = [4,8,12,16,20]
        self.fingersRaised = [0,0,0,0,0]
        self.handX = 0
        self.handY = 0
        self.handPositions = [[0,0] for i in range(frameSample)]
        self.mouse = Controller()
        self.clickThresh = 0.5
        self.lastClick = 0

        self.cap = cv2.VideoCapture(0)
        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(False, 1, False, 0.5, 0.5)
        self.mpDraw = mp.solutions.drawing_utils

    def avg(self,lst):
        if len(lst) > 0:
            return sum(lst) / len(lst)

    def avgSlope(self,lst): #input of a matrix of x,y positions
        deltaX = [] 
        deltaY = []
        for i in range(len(lst)):
            if i != len(lst) - 1:
                deltaX.append(lst[i+1][0] - lst[i][0])
                deltaY.append(lst[i+1][1] - lst[i][1])
        
        avgX = self.avg(deltaX)
        avgY = self.avg(deltaY)
        print("Slopes: ", [avgX, avgY])
        return [avgX, avgY]
    
    def avgPos(self,lst): #input of a matrix of x,y positions
        avgX = self.avg([x[0] for x in lst])
        avgY = self.avg([y[1] for y in lst])
        return [int(avgX), int(avgY)]   

    def queue(self,lst, point):
        newQueue = []
        for i in range(1,len(lst)):
            newQueue.append(lst[i])
        newQueue.append(point)
        return newQueue

    def suppressMotion(self, handLms, inverted = True, xScale = 2, yScale = 2, handOffsetX = 400, handOffsetY = 400):
        input_X = self.avg([handLms.landmark[item].x for item in [0,9,13]])
        input_Y = self.avg([handLms.landmark[item].y  for item in [0,9,13]])
        self.handX = int(input_X * (self.display[0] * xScale ) - handOffsetX)
        self.handY = int(input_Y * (self.display[1] * yScale) - handOffsetY)

        if inverted:
            self.handX = self.display[0] - self.handX #inverted for camera facing you

        if self.suppressShake:
            if abs(self.handX-self.prevX) > self.moveThresh or abs(self.handY - self.prevY) > self.moveThresh: #suppresses shaking
                self.prevX = self.handX
                self.prevY = self.handY
            
            self.handPositions = self.queue(self.handPositions, [self.handX, self.handY])
            self.handX = self.avgPos(self.handPositions)[0]
            self.handY = self.avgPos(self.handPositions)[1]
        
    def controlMouse(self):
        if self.fingersRaised.count(1) == 4:
            if self.mouseDown == False:
                self.mouse.press(Button.left)
                self.mouseDown = True
        else:
            self.mouseDown = False
            self.mouse.release(Button.left)
            if self.fingersRaised[1] == 1 and self.fingersRaised[2] == 1:
                if self.handY <= self.display[1]/2:
                    scroll = int((self.display[1]/2 -self.handY)/2)
                else:
                    scroll = int(-(self.handY - self.display[1]/2)/2)
                self.mouse.scroll(scroll,0)
            elif self.fingersRaised[1] == 1:
                if (time.time() - self.lastClick) > self.clickThresh:
                    self.mouse.click(Button.left,1)
                    self.lastClick = time.time()
            elif self.fingersRaised[2] == 1:
                self.mouse.click(Button.right,1)

    def draw(self):
        while True:
            sucesss,img = self.cap.read()
            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = self.hands.process(imgRGB)
            h,w,c = img.shape
            y_offset = 5 #vertical position offset for number label on finger landmarks 
            if results.multi_hand_landmarks:
                for handLms in results.multi_hand_landmarks:
                    self.mpDraw.draw_landmarks(img, handLms,self.mpHands.HAND_CONNECTIONS)
                    for id, lm in enumerate(handLms.landmark):
                        if self.drawHand:
                            cv2.putText(img, str(id), (int(lm.x * w), int(lm.y * h - y_offset)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        if id % 4 == 0 and id > 4:
                            if lm.y < handLms.landmark[id - 2].y:
                                self.fingersRaised[id // 4 - 1] = 1
                            else:
                                self.fingersRaised[id // 4 - 1] = 0
                    self.suppressMotion(handLms)
                    self.mouse.position = (self.handX, self.handY)
            
                
                self.controlMouse()
                    
            cTime = time.time()
            fps = round(1/(cTime - self.pTime),2)
            self.pTime = cTime

            cv2.putText(img,str(fps),(10,20),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,255,0),2) #self.displays fps
            cv2.imshow('Camera1',img) #shows camera feed
            cv2.waitKey(1) #waits for 1ms