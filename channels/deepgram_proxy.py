import asyncio
import base64
import json
import websockets
from pydub import AudioSegment

def deepgram_connect():
	extra_headers = {'Authorization': 'Token API_KEY'}
	deepgram_ws = websockets.connect("wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=2&multichannel=true", extra_headers = extra_headers)
	return deepgram_ws

async def proxy(client_ws):
	# inbox = asyncio.Queue() # not needed unless sending ws messages back to the client
	outbox = asyncio.Queue()

	print('started proxy')

	async with deepgram_connect() as deepgram_ws:
		async def deepgram_sender(deepgram_ws):
			print('started deepgram sender')
			while True:
				chunk = await outbox.get()
				await deepgram_ws.send(chunk)
				print('finished deepgram sender')

		async def deepgram_receiver(deepgram_ws):
			print('started deepgram receiver')
			async for message in deepgram_ws:
				try:
					dg_json = json.loads(message)
					print(dg_json)
				except:
					print('was not able to parse deepgram response as json')
					continue
			print('finished deepgram receiver')

		async def client_receiver(client_ws):
			print('started client receiver')

			BUFFER_SIZE = 20 * 160
			inbuffer = bytearray(b'')
			outbuffer = bytearray(b'')
			empty_byte_received = False
			inbound_chunks_started = False
			outbound_chunks_started = False
			latest_inbound_timestamp = 0
			latest_outbound_timestamp = 0
			async for message in client_ws:
				try:
					data = json.loads(message)
					if data["event"] in ("connected", "start"):
						print("Media WS: Received event connected or start")
						continue
					if data["event"] == "media":
						media = data["media"]
						chunk = base64.b64decode(media["payload"])
						if media['track'] == 'inbound':
							# fills in silence if there have been dropped packets
							if inbound_chunks_started:
								if latest_inbound_timestamp + 20 < int(media['timestamp']):
									bytes_to_fill = 8 * (int(media['timestamp']) - (latest_inbound_timestamp + 20))
									print ('INBOUND WARNING! last timestamp was ' + str(latest_inbound_timestamp) + ' but current packet is for timestamp ' + media['timestamp'] + ', filling in ' + str(bytes_to_fill) + ' bytes of silence')
									inbuffer.extend(b"\xff" * bytes_to_fill) # NOTE: 0xff is silence for mulaw audio, and there are 8 bytes per ms of data for our format (8 bit, 8000 Hz)
							else:
								print ('started receiving inbound chunks!')
								# make it known that inbound chunks have started arriving
								inbound_chunks_started = True
								latest_inbound_timestamp = int(media['timestamp'])
								# this basically sets the starting point for outbound timestamps
								latest_outbound_timestamp = int(media['timestamp']) - 20
							latest_inbound_timestamp = int(media['timestamp'])
							# extend the inbound audio buffer with data
							inbuffer.extend(chunk)
						if media['track'] == 'outbound':
							# make it known that outbound chunks have started arriving
							outbound_chunked_started = True
							# fills in silence if there have been dropped packets
							if latest_outbound_timestamp + 20 < int(media['timestamp']):
								bytes_to_fill = 8 * (int(media['timestamp']) - (latest_outbound_timestamp + 20))
								print ('OUTBOUND WARNING! last timestamp was ' + str(latest_outbound_timestamp) + ' but current packet is for timestamp ' + media['timestamp'] + ', filling in ' + str(bytes_to_fill) + ' bytes of silence')
								outbuffer.extend(b"\xff" * bytes_to_fill) # NOTE: 0xff is silence for mulaw audio, and there are 8 bytes per ms of data for our format (8 bit, 8000 Hz)
							latest_outbound_timestamp = int(media['timestamp'])
							# extend the outbound audio buffer with data
							outbuffer.extend(chunk)
						if chunk == b'':
							empty_byte_received = True
					if data["event"] == "stop":
						print("Media WS: Received event stop")
						break

					# check if our buffer is ready to send to our outbox (and, thus, then to deepgram)
					while len(inbuffer) >= BUFFER_SIZE and len(outbuffer) >= BUFFER_SIZE or empty_byte_received:
						if empty_byte_received:
							break

						print ( str(len(inbuffer)) + ' ' + str(len(outbuffer)) )
						asinbound = AudioSegment(inbuffer[:BUFFER_SIZE], sample_width=1, frame_rate=8000, channels=1)
						asoutbound = AudioSegment(outbuffer[:BUFFER_SIZE], sample_width=1, frame_rate=8000, channels=1)
						mixed = AudioSegment.from_mono_audiosegments(asinbound, asoutbound)
						outbox.put_nowait(mixed.raw_data)
						inbuffer = inbuffer[BUFFER_SIZE:]
						outbuffer = outbuffer[BUFFER_SIZE:]
				except:
					print('message from client not formatted correctly, bailing')
					break

			outbox.put_nowait(b'')
			print('finished client receiver')


		await asyncio.wait([
			asyncio.ensure_future(deepgram_sender(deepgram_ws)),
			asyncio.ensure_future(deepgram_receiver(deepgram_ws)),
			asyncio.ensure_future(client_receiver(client_ws))
		])

		client_ws.close()
		print('finished running the proxy')