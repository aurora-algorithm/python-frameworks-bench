# The vCPU split inside the rig, so the server, the load tool, Postgres and monitoring never share a core.
SERVER_CORES=2
OHA_CORES=6-8
POSTGRES_CORES=3-5
MONITOR_CORES=0-1
