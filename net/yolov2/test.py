import numpy as np
import math
import cv2
import os
#from scipy.special import expit
from utils.box import BoundBox, box_iou, prob_compare
from utils.box import prob_compare2, box_intersection


def expit(x):
	return 1. / (1. + np.exp(-x))

def _softmax(x):
    e_x = np.exp(x - np.max(x))
    out = e_x / e_x.sum()
    return out

def findboxes(self, net_out):
	# meta
	meta = self.meta
	H, W, _ = meta['out_size']
	threshold = meta['thresh']
	C, B = meta['classes'], meta['num']
	anchors = meta['anchors']
	net_out = net_out.reshape([H, W, B, -1])

	boxes = list()
	for row in range(H):
		for col in range(W):
			for b in range(B):
				bx = BoundBox(C)
				bx.x, bx.y, bx.w, bx.h, bx.c = net_out[row, col, b, :5]
				bx.c = expit(bx.c)
				bx.x = (col + expit(bx.x)) / W
				bx.y = (row + expit(bx.y)) / H
				bx.w = math.exp(bx.w) * anchors[2 * b + 0] / W
				bx.h = math.exp(bx.h) * anchors[2 * b + 1] / H
				classes = net_out[row, col, b, 5:]
				bx.probs = _softmax(classes) * bx.c
				bx.probs *= bx.probs > threshold
				boxes.append(bx)

	# non max suppress boxes
	for c in range(C):
		for i in range(len(boxes)):
			boxes[i].class_num = c
		boxes = sorted(boxes, key=prob_compare, reverse=True)
		for i in range(len(boxes)):
			boxi = boxes[i]
			if boxi.probs[c] == 0: continue
			for j in range(i + 1, len(boxes)):
				boxj = boxes[j]
				if box_iou(boxi, boxj) >= .4:
					boxes[j].probs[c] = 0.
	return boxes

def postprocess(self, net_out, im, save = True):
	"""
	Takes net output, draw net_out, save to disk
	"""
	boxes = self.findboxes(net_out)

	# meta
	meta = self.meta
	threshold = meta['thresh']
	colors = meta['colors']
	labels = meta['labels']
	if type(im) is not np.ndarray:
		imgcv = cv2.imread(im)
	else: imgcv = im
	h, w, _ = imgcv.shape
	
	textBuff = "["
	for b in boxes:
		boxResults = self.process_box(b, h, w, threshold)
		if boxResults is None:
			continue
		left, right, top, bot, mess, max_indx, confidence = boxResults
		thick = int((h + w) // 300)
		if self.FLAGS.json:
			line = 	('{"label":"%s",'
					'"confidence":%.2f,'
					'"topleft":{"x":%d,"y":%d},'
					'"bottomright":{"x":%d,"y":%d}},\n') % \
					(mess, confidence, left, top, right, bot)
			textBuff += line

		cv2.rectangle(imgcv,
			(left, top), (right, bot),
			colors[max_indx], thick)
		cv2.putText(imgcv, '{} ({:.2})'.format(mess,confidence), (left, top - 12),
			0, 1e-3 * h, colors[max_indx],thick//3)

	if not save: return imgcv, textBuff

	outfolder = os.path.join(self.FLAGS.test, 'out')
	img_name = os.path.join(outfolder, im.split('/')[-1])
	
	# Removing trailing comma+newline adding json list terminator.
	textBuff = textBuff[:-2] + "]"
	outfolder = os.path.join(self.FLAGS.test, 'out')
	img_name = os.path.join(outfolder, im.split('/')[-1])
	if self.FLAGS.json:
		textFile = os.path.splitext(img_name)[0] + ".json"
		with open(textFile, 'w') as f:
			f.write(textBuff)
		return

	cv2.imwrite(img_name, imgcv)
