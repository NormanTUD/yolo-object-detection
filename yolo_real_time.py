# USAGE
# python yolo_real_time.py --output output/airport_output.avi for saving the live video to a file
# python yolo_real_time.py for just live stream

from imutils.video import VideoStream
import numpy as np
import argparse
import imutils
import time
import cv2
import os
from pprint import pprint
import sys

def dier (msg):
	pprint(msg)
	sys.exit(0)

ap = argparse.ArgumentParser()
ap.add_argument("-o", "--output", default=False,
	help="path to output video")
ap.add_argument("-c", "--confidence", type=float, default=0.5,
	help="minimum probability to filter weak detections")
ap.add_argument("-s", "--blur-size", type=int, default=25,
	help="Blur pen size")
ap.add_argument("-t", "--threshold", type=float, default=0.3,
	help="threshold when applying non-maxima suppression")
ap.add_argument("-b", "--blur-inside", type=bool, default=False,
	help="Blur inside detection boxes")
ap.add_argument("-B", "--blur-outside", type=bool, default=False,
	help="Blur outside detection boxes")
ap.add_argument("-l", "--list-blurrable", type=str, default="",
	help="Comma-seperated list of items that should be blurred/not blurred with --blur-inside/--blur-outside")
args = vars(ap.parse_args())

def is_blurrable (list_blurrable, item):
	splitted = list_blurrable.split(',')
	if len(splitted) == 0:
		return 1
	else:
		for this_item in splitted:
			if this_item == item:
				return 1
	return 0

# load the COCO class labels our YOLO model was trained on
labelsPath = os.path.sep.join(["yolo-coco", "coco.names"])
LABELS = open(labelsPath).read().strip().split("\n")

COLORS = np.random.randint(0, 255, size=(len(LABELS), 3),
	dtype="uint8")

# derive the paths to the YOLO weights and model configuration
weightsPath = os.path.sep.join(["yolo-coco", "yolov3.weights"])
configPath = os.path.sep.join(["yolo-coco", "yolov3.cfg"])

# load our YOLO object detector trained on COCO dataset (80 classes) and determine only the *output* layer names that we need from YOLO
print("[INFO] loading YOLO from disk...")
net = cv2.dnn.readNetFromDarknet(configPath, weightsPath)
ln = net.getLayerNames()
ln = [ln[i[0] - 1] for i in net.getUnconnectedOutLayers()]

# check if the video writer is enabled
if args["output"] is not False:
	fourcc = cv2.VideoWriter_fourcc(*"MJPG")
	writer = cv2.VideoWriter(args["output"], fourcc, 2,(640, 360), True)

(W, H) = (None, None)
print("[INFO] starting video capture...")
cap = cv2.VideoCapture(0)
time.sleep(2.0)

while True:
	ret, frame = cap.read()
	frame = cv2.resize(frame, (640, 360))

	if W is None or H is None:
		(H, W) = frame.shape[:2]

	# construct a blob from the input frame and then perform a forward pass of the YOLO object detector,
	# giving us our bounding boxes and associated probabilities
	blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416),
		swapRB=True, crop=False)
	net.setInput(blob)
	start = time.time()
	layerOutputs = net.forward(ln)
	end = time.time()

	# initialize our lists of detected bounding boxes, confidences, and class IDs, respectively
	boxes = []
	confidences = []
	classIDs = []

	for output in layerOutputs: 	# loop over each of the layer outputs
		for detection in output:		# loop over each of the detections
			# extract the class ID and confidence (i.e., probability) of the current object detection
			scores = detection[5:]
			classID = np.argmax(scores)
			confidence = scores[classID]

			# filter out weak predictions by ensuring the detected probability is greater than the minimum probability
			if confidence > args["confidence"]:
				# scale the bounding box coordinates back relative to the size of the image, keeping in mind that YOLO
				# actually returns the center (x, y)-coordinates of the bounding box followed by the boxes' width and height
				box = detection[0:4] * np.array([W, H, W, H])
				(centerX, centerY, width, height) = box.astype("int")

				# use the center (x, y)-coordinates to derive the top and and left corner of the bounding box
				x = int(centerX - (width / 2))
				y = int(centerY - (height / 2))

				# update our list of bounding box coordinates, confidences, and class IDs
				boxes.append([x, y, int(width), int(height)])
				confidences.append(float(confidence))
				classIDs.append(classID)

	# apply non-maxima suppression to suppress weak, overlapping bounding boxes
	idxs = cv2.dnn.NMSBoxes(boxes, confidences, args["confidence"],
		args["threshold"])

	# ensure at least one detection exists
	if len(idxs) > 0:
		# loop over the indexes we are keeping
		if args["blur_inside"] and args["blur_outside"]:
			frame = cv2.GaussianBlur(frame, (int(args["blur_size"]), int(args["blur_size"])), 0)
		elif args["blur_inside"]:
			for i in idxs.flatten():
				if is_blurrable(args["list_blurrable"], LABELS[classIDs[i]]):
					# extract the bounding box coordinates
					(x, y) = (boxes[i][0], boxes[i][1])
					(w, h) = (boxes[i][2], boxes[i][3])

					end_x = x + w
					end_y = y + h

					blurred = cv2.GaussianBlur(frame, (int(args["blur_size"]), int(args["blur_size"])), 0)
					frame[y:end_y, x:end_x] = blurred[y:end_y, x:end_x]
		elif args["blur_outside"]:
			original_frame = frame
			frame = cv2.GaussianBlur(frame, (int(args["blur_size"]), int(args["blur_size"])), 0)
			for i in idxs.flatten():
				if is_blurrable(args["list_blurrable"], LABELS[classIDs[i]]):
					# extract the bounding box coordinates
					(x, y) = (boxes[i][0], boxes[i][1])
					(w, h) = (boxes[i][2], boxes[i][3])

					end_x = x + w
					end_y = y + h

					frame[y:end_y, x:end_x] = original_frame[y:end_y, x:end_x]
		for i in idxs.flatten():
			# extract the bounding box coordinates
			(x, y) = (boxes[i][0], boxes[i][1])
			(w, h) = (boxes[i][2], boxes[i][3])

			# draw a bounding box rectangle and label on the frame
			color = [int(c) for c in COLORS[classIDs[i]]]

			cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
			text = "{}: {:.4f}".format(LABELS[classIDs[i]],
				confidences[i])
			cv2.putText(frame, text, (x, y - 5),
				cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

	if args["output"] is not False:
		writer.write(frame)

	cv2.imshow("Output", frame)
	if cv2.waitKey(1) & 0xFF == ord('q'):
		break

print("[INFO] cleanup up...")
if args["output"] is not False:
	writer.release()
cap.release()
cv2.destroyAllWindows()
