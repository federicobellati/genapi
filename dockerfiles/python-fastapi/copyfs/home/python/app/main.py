
################## IMPORT LIBRARIES #####################
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from endpoints import router


####################  DEFINE  #########################

app = FastAPI(title="GENAPI")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(?:[a-zA-Z0-9-]+\.)+ve\.ismar\.cnr\.it(?::\d{1,5})?", allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
app.include_router(router)

#######################################################


####################  A P I   C A L L S ###############

####################################


#########################################################
##
##               M A I N
##
#########################################################

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)
