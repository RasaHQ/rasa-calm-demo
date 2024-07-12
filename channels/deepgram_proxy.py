import asyncio
import base64
import json
import websockets
from pydub import AudioSegment

def deepgram_connect():
	extra_headers = {'Authorization': 'Token d51e0421ea4c82735550f6f22be0e256edfc0fc1'}
	deepgram_ws = websockets.connect("wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=2&multichannel=true", extra_headers = extra_headers)
	return deepgram_ws

async def client_receiver(client_ws):
	print('started client receiver')
	BUFFER_SIZE = 20 * 240
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
				print(media)
				chunk = base64.b64decode(media["payload"])
				inbuffer.extend(chunk)
			if data["event"] == "stop":
				print("Media WS: Received event stop")
				break
			# check if our buffer is ready to send to our outbox (and, thus, then to deepgram)
			while len(inbuffer) >= BUFFER_SIZE or empty_byte_received:
				if empty_byte_received:
					break
				print ( str(len(inbuffer)) + ' ' + str(len(outbuffer)) )
				asyncio.ensure_future(deepgram_proxy(inbuffer[:BUFFER_SIZE]))
				inbuffer = inbuffer[BUFFER_SIZE:]
				
		except:
			print('message from client not formatted correctly, bailing')
			break

async def deepgram_proxy(outbox):
	async with deepgram_connect() as deepgram_ws:
			await deepgram_ws.send(outbox)
			print('finished deepgram sender')
			print('started deepgram receiver')
			async for message in deepgram_ws:
				try:
					dg_json = json.loads(message)
					print(dg_json)
				except:
					print('was not able to parse deepgram response as json')
					continue
			print('finished deepgram receiver')

