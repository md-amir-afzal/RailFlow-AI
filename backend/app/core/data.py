"""Clearly synthetic demonstration data for RailFlow AI."""
from datetime import datetime, timedelta

STATIONS = [
 {"code":"NDLS","name":"New Delhi","city":"Delhi","lat":28.643,"lon":77.219,"zone":"Northern Railway"},
 {"code":"AGC","name":"Agra Cantt","city":"Agra","lat":27.157,"lon":77.991,"zone":"North Central Railway"},
 {"code":"GWL","name":"Gwalior","city":"Gwalior","lat":26.218,"lon":78.182,"zone":"North Central Railway"},
 {"code":"JHS","name":"Virangana Lakshmibai Jhansi","city":"Jhansi","lat":25.448,"lon":78.569,"zone":"North Central Railway"},
 {"code":"BPL","name":"Bhopal Junction","city":"Bhopal","lat":23.268,"lon":77.413,"zone":"West Central Railway"},
 {"code":"NGP","name":"Nagpur","city":"Nagpur","lat":21.146,"lon":79.088,"zone":"Central Railway"},
 {"code":"MMR","name":"Manmad Junction","city":"Manmad","lat":20.251,"lon":74.438,"zone":"Central Railway"},
 {"code":"CSMT","name":"Mumbai CSMT","city":"Mumbai","lat":18.939,"lon":72.835,"zone":"Central Railway"},
 {"code":"JP","name":"Jaipur Junction","city":"Jaipur","lat":26.919,"lon":75.787,"zone":"North Western Railway"},
 {"code":"KOTA","name":"Kota Junction","city":"Kota","lat":25.213,"lon":75.864,"zone":"West Central Railway"},
 {"code":"ADI","name":"Ahmedabad Junction","city":"Ahmedabad","lat":23.027,"lon":72.601,"zone":"Western Railway"},
 {"code":"LKO","name":"Lucknow NR","city":"Lucknow","lat":26.846,"lon":80.946,"zone":"Northern Railway"},
]
# Edges are illustrative corridors, not a complete or authoritative track graph.
EDGES = [
 ("NDLS","AGC",190,2),("AGC","GWL",120,2),("GWL","JHS",100,2),("JHS","BPL",290,2),("BPL","NGP",350,2),("NGP","MMR",400,2),("MMR","CSMT",260,2),
 ("NDLS","JP",310,2),("JP","KOTA",240,2),("KOTA","BPL",280,2),("KOTA","ADI",500,1),("ADI","MMR",450,2),("NDLS","LKO",510,2),("LKO","JHS",300,2),("JP","ADI",650,1)
]
BASE = datetime(2026, 11, 9, 8, 0)
TRAINS = [
 {"id":"12951","name":"Mumbai Rajdhani (Demo)","category":"Superfast","origin":"NDLS","destination":"CSMT","route":["NDLS","AGC","GWL","JHS","BPL","NGP","MMR","CSMT"],"priority":5,"scheduled_departure":BASE.isoformat(),"delay_min":18,"speed_kmph":92,"status":"Delayed"},
 {"id":"12002","name":"Shatabdi Express (Demo)","category":"Express","origin":"NDLS","destination":"JP","route":["NDLS","JP"],"priority":4,"scheduled_departure":(BASE+timedelta(minutes=15)).isoformat(),"delay_min":4,"speed_kmph":105,"status":"On time"},
 {"id":"19804","name":"Kota Intercity (Demo)","category":"Passenger","origin":"JP","destination":"BPL","route":["JP","KOTA","BPL"],"priority":2,"scheduled_departure":(BASE+timedelta(minutes=28)).isoformat(),"delay_min":31,"speed_kmph":65,"status":"Delayed"},
 {"id":"22691","name":"Bengaluru Express (Demo)","category":"Express","origin":"NDLS","destination":"LKO","route":["NDLS","LKO"],"priority":3,"scheduled_departure":(BASE+timedelta(minutes=42)).isoformat(),"delay_min":0,"speed_kmph":88,"status":"On time"},
 {"id":"11058","name":"Vidarbha Express (Demo)","category":"Express","origin":"NGP","destination":"CSMT","route":["NGP","MMR","CSMT"],"priority":3,"scheduled_departure":(BASE+timedelta(minutes=55)).isoformat(),"delay_min":12,"speed_kmph":78,"status":"Delayed"},
 {"id":"59012","name":"Goods Special (Demo)","category":"Freight","origin":"BPL","destination":"NGP","route":["BPL","NGP"],"priority":1,"scheduled_departure":(BASE+timedelta(minutes=65)).isoformat(),"delay_min":7,"speed_kmph":55,"status":"On time"},
]
