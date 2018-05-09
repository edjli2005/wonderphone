 #!/usr/bin/env python3

# Script by Edward Li
# Updated Sept 17, 2017

import time, os, sys, subprocess, signal, logging, math
import RPi.GPIO as GPIO
from os import listdir
from os.path import isfile, join
from random import *

GPIO.setmode(GPIO.BCM)

logger = logging.getLogger('logwonderphone')
handler = logging.FileHandler('/home/pi/Desktop/wonderphone.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
#dwc_otg.fiq_split_enable=0


# read SPI data from MCP3008 chip, 8 possible adc's (0 thru 7)
def readadc(adcnum, clockpin, mosipin, misopin, cspin):
	if ((adcnum > 7) or (adcnum < 0)):
		return -1
	GPIO.output(cspin, True)
	
	GPIO.output(clockpin, False)  # start clock low
	GPIO.output(cspin, False)     # bring CS low
	
	commandout = adcnum
	commandout |= 0x18  # start bit + single-ended bit
	commandout <<= 3    # we only need to send 5 bits here
	for i in range(5):
		if (commandout & 0x80):
			GPIO.output(mosipin, True)
		else:
			GPIO.output(mosipin, False)
		commandout <<= 1
		GPIO.output(clockpin, True)
		GPIO.output(clockpin, False)
	
	adcout = 0
	# read in one empty bit, one null bit and 10 ADC bits
	for i in range(12):
		GPIO.output(clockpin, True)
		GPIO.output(clockpin, False)
		adcout <<= 1
		if (GPIO.input(misopin)):
			adcout |= 0x1
	
	GPIO.output(cspin, True)
	
	adcout >>= 1       # first bit is 'null' so drop it
	return adcout

# pins connected from the SPI port on the ADC to the Cobbler
SPICLK = 18
SPIMISO = 23
SPIMOSI = 24
SPICS = 25
GPIO.setup(SPIMOSI, GPIO.OUT)
GPIO.setup(SPIMISO, GPIO.IN)
GPIO.setup(SPICLK, GPIO.OUT)
GPIO.setup(SPICS, GPIO.OUT)


# pins connected from various I/O to the Cobbler
PRESSED = 20
HOOK = 8
EXIT = 21
GPIO.setup(PRESSED, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
GPIO.setup(HOOK, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)
GPIO.setup(EXIT, GPIO.IN, pull_up_down = GPIO.PUD_UP)

# debug enable
DEBUG_RAWADC = 0
DEBUG_PRESSED = 1
DEBUG_HOOK = 1

# global vars
MENU = 0
HOOKCOUNT = 0

# play wav file on the attached system sound device
def play_wav(wav_filename):
	global p
	msg = "playing " + ", ".join(wav_filename)
	logger.debug(msg)
	p = subprocess.Popen(
		['aplay','-i','-D','plughw:1'] + wav_filename,
		stdin = subprocess.PIPE,
		stdout = subprocess.PIPE,
		stderr = subprocess.STDOUT,
		shell = False
	)
	
# play wav file on the attached system sound device
def play_multiple_wav(wav_filename1, wav_filename2):
	global p
	msg = "playing " + wav_filename1 + " " + wav_filename2
	logger.debug(msg)
	p = subprocess.Popen(
		['aplay','-i','-D','plughw:1', wav_filename1, wav_filename2],
		stdin = subprocess.PIPE,
		stdout = subprocess.PIPE,
		stderr = subprocess.STDOUT,
		shell = False
	)

# record wav file on the attached system sound device
def record_wav(wav_filename):
	global r
	r = subprocess.Popen(
		['arecord','-f','cd','-d','30','-t','wav','-D','plughw:1','--max-file-time','30',wav_filename],
		stdin = subprocess.PIPE,
		stdout = subprocess.PIPE,
		stderr = subprocess.STDOUT,
		shell = False
	)
	print(r.stdout.read())

# find a random file in the recordings to play
def find_file(path):
	files = [f for f in listdir(path) if isfile(join(path, f))]
	#print files
	#print len(files)
	x = 0
	x = randrange(len(files))
	#print x
	filename = path + "/" + files[x]
	#print(filename)
	return filename

# determine what to do when a button is pressed
def button_pressed(channel):
	global MENU
	if GPIO.input(HOOK) == 1:
		btnval = readadc(0, SPICLK, SPIMOSI, SPIMISO, SPICS) # check value of ADC
		if DEBUG_RAWADC:
			print ("btnval:", btnval)
			
		if btnval > 980: # 1
			if p.poll() == None:
				p.kill()
			# English selected
			if MENU == -1:
				if DEBUG_PRESSED:
					print("1 ENGLISH")
					logger.debug("1")
				MENU = 1
				play_wav(["/media/pi/WONDERPHONE/prompts/en/MainMenu.wav"])
			# English selected --> Story from Dallas' Past
			elif MENU == 1:
				if DEBUG_PRESSED:
					print("11 Story from Dallas' Past.")
					logger.debug("11")
				MENU = 11
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu1.wav", "/media/pi/WONDERPHONE/stories/1/PersonalStory.wav"])
			# Spanish selected --> Story from Dallas' Past
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("21 Story from Dallas' Past. (Spanish)")
					logger.debug("21")
				MENU = 21
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu1.wav","/media/pi/WONDERPHONE/stories/1/PersonalStory.wav"])
			# English selected --> Personal Prompt --> Recording
			elif MENU == 17:
				if DEBUG_PRESSED:
					print("171 Recording Personal Prompt.")
					logger.debug("171")
				MENU = 171
				play_wav(["/media/pi/WONDERPHONE/prompts/recordtone.wav"])
				p.wait()
				year, month, day, hour, minute, second = time.strftime("%Y,%m,%d,%H,%M,%S").split(',')
				savename = "/media/pi/WONDERPHONE/recordings/en/" + year + month + day + "-" + hour + minute + second + ".wav"
				print("recording started")
				logger.debug("recording started")
				record_wav(savename)
				print("recording stopped")
				logger.debug("recording stopped")
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Finish7.wav"])
			# Spanish selected --> Personal Prompt --> Recording
			elif MENU == 27:
				if DEBUG_PRESSED:
					print("271 Recording Personal Prompt. (Spanish)")
					logger.debug("271")
				MENU = 271
				play_wav(["/media/pi/WONDERPHONE/prompts/recordtone.wav"])
				p.wait()
				year, month, day, hour, minute, second = time.strftime("%Y,%m,%d,%H,%M,%S").split(',')
				savename = "/media/pi/WONDERPHONE/recordings/es/" + year + month + day + "-" + hour + minute + second + ".wav"
				print("recording started")
				logger.debug("recording started")
				record_wav(savename)
				print("recording stopped")
				logger.debug("recording stopped")
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Finish7.wav"])
			else:
				print("New menu val " + str(math.floor(MENU/10)))
				while(MENU > 2):
					MENU = math.floor(MENU/10)
	
		if btnval > 870 and btnval < 910: # 2
			if p.poll() == None:
				p.kill()
			# Spanish selected
			if MENU == -1:
				if DEBUG_PRESSED:
					print("2 SPANISH")
					logger.debug("2")
				MENU = 2
				play_wav(["/media/pi/WONDERPHONE/prompts/es/MainMenu.wav"])
			# English selected --> Story about Dallas' Future
			elif MENU == 1:
				if DEBUG_PRESSED:
					print("12 Story about Dallas' Future.")
					logger.debug("12")
				MENU = 12
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu2.wav", "/media/pi/WONDERPHONE/stories/2/FutureStory.wav"])
			# Spanish selected --> Story about Dallas' Future
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("22 Story about Dallas' Future. (Spanish)")
					logger.debug("22")
				MENU = 22
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu2.wav", "/media/pi/WONDERPHONE/stories/2/FutureStory.wav"])
			
		if btnval > 760 and btnval < 810: # 3
			if p.poll() == None:
				p.kill()
			# English selected --> Action Prompt
			if MENU == 1:
				if DEBUG_PRESSED:
					print("13 Action Prompt.")
					logger.debug("13")
				MENU = 13
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu3.wav", "/media/pi/WONDERPHONE/prompts/en/Prompt3.wav"])
			# Spanish selected --> Action Prompt
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("23 Action Prompt. (Spanish)")
					logger.debug("23")
				MENU = 23
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu3.wav", "/media/pi/WONDERPHONE/prompts/es/Prompt3.wav"])
				
		if btnval > 700 and btnval < 750: # 4
			if p.poll() == None:
				p.kill()
			# English selected --> Historical Wonder
			if MENU == 1:
				if DEBUG_PRESSED:
					print("14 Historical Wonder.")
					logger.debug("14")
				MENU = 14
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu4.wav", "/media/pi/WONDERPHONE/stories/4/HistoryStory.wav"])
			# Spanish selected --> Action Prompt
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("24 Historical Wonder. (Spanish)")
					logger.debug("24")
				MENU = 24
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu4.wav", "/media/pi/WONDERPHONE/stories/4/HistoryStory.wav"])
				
		if btnval > 650 and btnval < 670: # 5
			if p.poll() == None:
				p.kill()
			# English selected --> Architectural Wonder
			if MENU == 1:
				if DEBUG_PRESSED:
					print("15 Architectural Wonder.")
					logger.debug("15")
				MENU = 15
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu5.wav", "/media/pi/WONDERPHONE/stories/5/ArchitectureStory.wav"])
			# Spanish selected --> Architectural Wonder
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("25 Architectural Wonder. (Spanish)")
					logger.debug("25")
				MENU = 25
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu5.wav", "/media/pi/WONDERPHONE/stories/5/ArchitectureStory.wav"])
				
		if btnval > 580 and btnval < 610: # 6
			if p.poll() == None:
				p.kill()
			# English selected --> Musical Wonder
			if MENU == 1:
				if DEBUG_PRESSED:
					print("16 Musical Wonder.")
					logger.debug("16")
				MENU = 16
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu6.wav", "/media/pi/WONDERPHONE/stories/6/GarageGrooves1.wav"])
			# Spanish selected --> Musical Wonder
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("26 Musical Wonder. (Spanish)")
					logger.debug("26")
				MENU = 26
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu6.wav", "/media/pi/WONDERPHONE/stories/6/GarageGrooves1.wav"])
				
		if btnval > 540 and btnval < 570: # 7
			if p.poll() == None:
				p.kill()
			# English selected --> Personal Prompt
			if MENU == 1:
				if DEBUG_PRESSED:
					print("17 Personal Prompt.")
					logger.debug("17")
				MENU = 17
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu7.wav", "/media/pi/WONDERPHONE/prompts/en/Prompt7.wav", "/media/pi/WONDERPHONE/prompts/en/Ready7.wav"])
			# Spanish selected --> Personal Prompt
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("27 Personal Prompt. (Spanish)")
					logger.debug("27")
				MENU = 27
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu7.wav", "/media/pi/WONDERPHONE/prompts/es/Prompt7.wav", "/media/pi/WONDERPHONE/prompts/es/Ready7.wav"])
				
		if btnval > 500 and btnval < 525: # 8
			if p.poll() == None:
				p.kill()
			# English selected --> Personal Responses 
			if MENU == 1:
				if DEBUG_PRESSED:
					print("18 Personal Responses.")
					logger.debug("18")
				MENU = 18
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu8.wav", "/media/pi/WONDERPHONE/prompts/en/Prompt8.wav", "/media/pi/WONDERPHONE/prompts/en/Finish8.wav"])
				p.wait()
				filename = find_file("/media/pi/WONDERPHONE/recordings/en")
				play_wav([filename])
				
			# Spanish selected --> Personal Responses
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("28 Personal Responses. (Spanish)")
					logger.debug("28")
				MENU = 28
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu8.wav", "/media/pi/WONDERPHONE/prompts/es/Prompt8.wav", "/media/pi/WONDERPHONE/prompts/es/Finish8.wav"])
				p.wait()
				filename = find_file("/media/pi/WONDERPHONE/recordings/es")
				play_wav([filename])
				
		if btnval > 470 and btnval < 490: # 9
			if p.poll() == None:
				p.kill()
			# English selected --> Wonder Hunt
			if MENU == 1:
				if DEBUG_PRESSED:
					print("19 Wonder Hunt.")
					logger.debug("19")
				MENU = 19
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu9.wav", "/media/pi/WONDERPHONE/prompts/en/Prompt9.wav"])
			# Spanish selected --> Wonder Hunt
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("29 Wonder Hunt. (Spanish)")
					logger.debug("29")
				MENU = 29
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu9.wav", "/media/pi/WONDERPHONE/prompts/es/Prompt9.wav"])
				
		if btnval > 420 and btnval < 440: # 0
			if p.poll() == None:
				p.kill()
			# English selected --> About Wonderphone
			if MENU == 1:
				if DEBUG_PRESSED:
					print("10 About Wonderphone.")
					logger.debug("10")
				MENU = 10
				play_wav(["/media/pi/WONDERPHONE/prompts/en/Menu10.wav"])
			# Spanish selected --> About Wonderphone
			elif MENU == 2:
				if DEBUG_PRESSED:
					print("20 About Wonderphone. (Spanish)")
					logger.debug("20")
				MENU = 20
				play_wav(["/media/pi/WONDERPHONE/prompts/es/Menu10.wav"])
				
		if btnval > 445 and btnval < 470: # star
			try:
				if p.poll() == None:
					p.kill()
			except NameError:
				print ("p doesn't exist")
			try:
				if r.poll() == None:
					r.kill()
			except NameError:
				print ("r doesn't exist")
			# English selected --> Return to English menu
			if MENU < 20 and MENU >= 10  or MENU >= 100 and MENU < 200:
				if DEBUG_PRESSED:
					print("STAR Return to English menu.")
					logger.debug("STAR")
					print("English Menu.")
					logger.debug("English Menu.")
				play_wav(["/media/pi/WONDERPHONE/prompts/en/MainMenu.wav"])
				MENU = 1
			# Spanish selected --> Return to Spanish menu
			elif MENU < 30 and MENU >= 20 or MENU >= 200 and MENU < 300:
				if DEBUG_PRESSED:
					print("STAR Return to Spanish menu.")
					logger.debug("STAR")
					print("Spanish Menu.")
					logger.debug("Spanish Menu.")
				play_wav(["/media/pi/WONDERPHONE/prompts/es/MainMenu.wav"])
				MENU = 2
		
		if btnval > 390 and btnval < 420: # pound
			try:
				if p.poll() == None:
					p.kill()
			except NameError:
				print ("p doesn't exist")
			try:
				if r.poll() == None:
					r.kill()
			except NameError:
				print ("r doesn't exist")
			# English selected --> Return to English menu
			if MENU < 20 and MENU >= 10  or MENU >= 100 and MENU < 200:
				if DEBUG_PRESSED:
					print("POUND Return to English menu.")
					logger.debug("POUND")
					print("English Menu.")
					logger.debug("English Menu.")
				play_wav(["/media/pi/WONDERPHONE/prompts/en/MainMenu.wav"])
				MENU = 1
			# Spanish selected --> Return to Spanish menu
			elif MENU < 30 and MENU >= 20 or MENU >= 200 and MENU < 300:
				if DEBUG_PRESSED:
					print("POUND Return to Spanish menu.")
					logger.debug("POUND")
					print("Spanish Menu.")
					logger.debug("Spanish Menu.")
				play_wav(["/media/pi/WONDERPHONE/prompts/es/MainMenu.wav"])
				MENU = 2

# phone hook: start the phone menu on switch off
def phone_hook(channel):
	global MENU
	global HOOKCOUNT
	hookval = GPIO.input(HOOK) # check value of hook switch
	#if hookval == 1:

	if DEBUG_HOOK:
		print(hookval, "Phone off hook.")
	if DEBUG_PRESSED:
		print("Main Menu.")
		logger.debug("Main Menu.")
	MENU = -1
	HOOKCOUNT += 1
	msg = "Phone off hook. HOOKCOUNT: " + str(HOOKCOUNT)
	logger.debug(msg)
	try:
		if p.poll() == None:
			p.kill()
			print("MEF: ending current playback; returning to main menu")
	except NameError:
		print("MEF: error; p does not exist")


	wav_file = "/media/pi/WONDERPHONE/prompts/languageselect.wav"
	play_wav([wav_file])

def main():
	try:
		phone_hook(HOOK)
		logger.debug("---------PROGRAM START---------")
		print("Waiting for action...")
		GPIO.add_event_detect(PRESSED, GPIO.RISING, callback=button_pressed, bouncetime=500) # look for button presses
		GPIO.add_event_detect(HOOK, GPIO.BOTH, callback=phone_hook, bouncetime=100) # look for phone on hook
		GPIO.wait_for_edge(EXIT, GPIO.RISING) # wait for exit button
		print("Quitting program.")
		print("hookcount total:", HOOKCOUNT)
		msg = "hookcount total:" + str(HOOKCOUNT)
		logger.debug(msg)
		logger.debug("----------PROGRAM END----------")
		try:
			if p.poll() == None:
				p.kill()
		except NameError:
			print ("p doesn't exist")
		try:
			if r.poll() == None:
				r.kill()
		except NameError:
			print ("r doesn't exist")
	except KeyboardInterrupt:
		try:
			if p.poll() == None:
				p.kill()
		except NameError:
			print ("p doesn't exist")
		try:
			if r.poll() == None:
				r.kill()
		except NameError:
			print ("r doesn't exist")
		GPIO.cleanup()		# clean up GPIO on CTRL+C exit
	sys.exit(0)				# system exit
	GPIO.cleanup()			# clean up GPIO on normal exit

if __name__ == "__main__":
	main()
