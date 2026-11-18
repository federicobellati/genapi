
################## IMPORT LIBRARIES #####################
from fastapi import FastAPI, HTTPException, Query, Depends, status
import os
import requests


####################  DEFINE  #########################

#######################################################


####################  A P I   C A L L S ###############

@app.get("/status")
async def status():
	"""
	Endpoint di test per verificare che il servizio sia attivo.
	
	Restituisce:
	- "pong" se il servizio è attivo.
	"""
	return {"message": "pong"}
####################################


#########################################################
##
##               M A I N
##
#########################################################

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)