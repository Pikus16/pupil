import os, sys

import glumpy 
import OpenGL.GL as gl
import OpenGL.GLUT as glut
import glumpy.atb as atb
from ctypes import *
import numpy as np

import cv2

# from gl_shapes import Point
from multiprocessing import Pipe, Value
from methods import denormalize
from gl_shapes import Point

from time import sleep


class Bar(atb.Bar):
	"""docstring for Bar"""
	def __init__(self, name, data_path, total_frames, framelist, defs):
		super(Bar, self).__init__(name,**defs) 
		self.fps = 0.0 
		self.play = c_bool(0)
		self.get_single = c_bool(0)
		self.frame_num = c_int(0)
		self.display = 1
		self.exit = c_bool(0)
		self.framelist = framelist
		self.data_path = data_path


		self.add_var("Play", self.play, key="SPACE", help="Play/Pause") #key="SPACE",
		self.add_var("FPS", step=0.01, getter=self.get_fps)
		# self.add_var("Frame Number", step=1, getter=self.get_frame_num, setter=self.set_frame_num,
		# 			help="Scrub through video frames.",
		# 			min=0, max=10)
		self.add_var("Frame Number", self.frame_num, min=0, max=total_frames-1)
		self.add_var("Display", step=1, getter=self.get_display, setter=self.set_display,
					max=2, min=0)
		self.add_button("Step", self.step_forward, key="s", help="Step forward one frame")
		self.add_button("Save Keyframe", self.add_keyframe, key="RETURN", help="Save keyframe to list")

		self.add_var("Exit", self.exit)

	def update_fps(self, dt):
		temp_fps = 1/dt
		self.fps += 0.1*(temp_fps-self.fps)

	def get_fps(self):
		return self.fps

	def screen_cap(self):
		# just flip the switch
		self.screen_shot = not self.screen_shot

	def get_frame_num(self):
		return self.frame_num
	def set_frame_num(self, val):
		self.frame_num = val

	def get_display(self):
		return self.display
	def set_display(self, val):
		self.display = val

	def step_forward(self):
		# just flip the switch
		self.get_single = 1

	def add_keyframe(self):
		if not self.frame_num.value in self.framelist.keyframes:
			print "Added Keyframe: %s to the list" %(self.frame_num.value)
			self.framelist.keyframes.append(self.frame_num.value)
			print "Keyframes:\n%s" %(self.framelist.keyframes)
			print "Number of Keyframes:\n%s" %(len(self.framelist.keyframes))
		else:
			print "Removing Keyframe"
			self.framelist.keyframes.remove(self.frame_num.value)
		if len(self.framelist.keyframes) > 1:
			self.framelist.keyframes = sorted(self.framelist.keyframes)
			self.framelist.otherframes = range(self.framelist.keyframes[0], self.framelist.keyframes[-1])
			
			self.framelist.otherframes = [i for i in self.framelist.otherframes if i not in self.framelist.keyframes]

			print "Non Keyframes:\n%s" %(self.framelist.otherframes)
			print "Number of Non Keyframes:\n%s" %(len(self.framelist.otherframes))

		np.save(os.path.join(self.data_path, "keyframes.npy"), np.asarray(self.framelist.keyframes))
		np.save(os.path.join(self.data_path, "otherframes.npy"), np.asarray(self.framelist.otherframes))


class Temp(object):
	"""Temp class to make objects"""
	def __init__(self):
		pass

def browser(data_path, pipe_video, frame_num, pts_path, pipe):

	# Get image array from queue, initialize glumpy, map img_arr to opengl texture 
	total_frames = pipe_video.recv()

	img_arr = cv2.cvtColor(pipe_video.recv(), cv2.COLOR_BGR2RGB)
	fig = glumpy.figure((img_arr.shape[1], img_arr.shape[0]))
	image = glumpy.Image(img_arr)
	image.x, image.y = 0,0

	# gaze object
	gaze = Temp()
	gaze.list = np.load(pts_path)
	gaze.x_pos = gaze.list[:,0]
	gaze.y_pos = gaze.list[:,1]
	gaze.dt = gaze.list[:,2]
	gaze_point = Point(color=(255,0,0,0.3), scale=60.0)

	# keyframe list object
	framelist = Temp()
	framelist.keyframes = []
	framelist.otherframes = []


	atb.init()
	bar = Bar("Browser", data_path, total_frames, framelist, dict(label="Controls",
			help="Scene controls", color=(50,50,50), alpha=50,
			text='light', position=(10, 10), size=(200, 440)))

	def draw():
		gaze_point.draw()


	def on_draw():
		fig.clear(0.0, 0.0, 0.0, 1.0)
		image.draw(x=image.x, y=image.y, z=0.0, 
					width=fig.width, height=fig.height)
		draw()

	def on_idle(dt):
		bar.update_fps(dt)

		if bar.play or bar.get_single:
			pipe.send(bar.play)
			img = pipe_video.recv()
			
			bar.frame_num.value = frame_num.value
			gaze.x_screen, gaze.y_screen = denormalize((gaze.x_pos[bar.frame_num.value], 
														gaze.y_pos[bar.frame_num.value]), 
														fig.width, fig.height)
			x_screen_cv, y_screen_cv = denormalize((gaze.x_pos[bar.frame_num.value], 
														gaze.y_pos[bar.frame_num.value]), 
														fig.width, fig.height, flip_y=False)

			if bar.display == 0:
				img_arr[...] = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)	
				gaze_point.update((0.0, 0.0))
			if bar.display == 1:
				img_arr[...] = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)	
				gaze_point.update((	gaze.x_screen, gaze.y_screen))
			if bar.display == 2:
				# draw foveal point
				img = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
				# img_blur = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), (0,0), 10)#np.zeros(img.shape, dtype='uint8')
				# img_blur = np.dstack((img_blur, img_blur, img_blur))

				mask_black_dot = 255*np.ones((img.shape[0], img.shape[1]), dtype='uint8') #(img_arr.shape[0], img_arr.shape[1])
				cv2.circle(mask_black_dot, (int(x_screen_cv), int(y_screen_cv)), 30, (0,0,0), -1)

				cv2.bitwise_xor(img, img, img, mask_black_dot)

 				img_arr[...] = img #np.dstack((img,img,img))
				gaze_point.update((0.0, 0.0))	
			bar.get_single = 0
	
		# else:
		# 	sleep(0.5)

		

		image.update()
		fig.redraw()
		if bar.exit:
			pass
			#fig.window.stop()
	

	fig.window.push_handlers(on_idle)
	fig.window.push_handlers(atb.glumpy.Handlers(fig.window))
	fig.window.push_handlers(on_draw)	
	fig.window.set_title("Browser")
	fig.window.set_position(0,0)	
	glumpy.show() 	