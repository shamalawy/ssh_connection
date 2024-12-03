from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import re
import models
import schemas
import connection_manager
from database import engine, get_db

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

import models
import schemas
import connection_manager
from database import engine, get_db

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Network SSH Connection Manager")

class CommandRequest(BaseModel):
    hostname: str
    command: str
    enable_mode: Optional[bool] = False

def starts_with_show_and_space(show_command):
    pattern = r'^show\s'
    return bool(re.match(pattern, show_command))

@app.post("/connections/command")
def execute_command(
    # hostname: str, 
    command_request: CommandRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a command on a specific network device
    """
    hostname = command_request.hostname

    if not starts_with_show_and_space(command_request.command):
        return {"respone": "Only supports show commands"}
    
    # Find the connection
    if hostname not in connection_manager.connection_manager.connections:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        # Get the SSH connection
        ssh_conn = connection_manager.connection_manager.connections[hostname]['ssh_conn']
        
        # Optional: Enter enable mode if requested
        if command_request.enable_mode:
            ssh_conn.enable()
        
        # Execute the command
        output = ssh_conn.send_command(command_request.command)
        
        # return {
        #     "hostname": hostname,
        #     "command": command_request.command,
        #     "output": output
        # }
        
        return output
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Command execution error: {str(e)}")

@app.post("/connections/mdcommand")
def execute_command(
    command_request: CommandRequest,
    db: Session = Depends(get_db)
):
    """
    Execute a command on a specific network device or all devices matching a partial hostname
    """
    hostname = command_request.hostname
    
    if not starts_with_show_and_space(command_request.command):
        return "Only supports show commands"
    # Find all connections that match the partial hostname
    matching_connections = db.query(models.NetworkConnection).filter(
        models.NetworkConnection.hostname.ilike(f"%{hostname}%")
    ).all()
    
    if not matching_connections:
        raise HTTPException(status_code=404, detail="No matching connections found")
    
    results = []
    
    for connection in matching_connections:
        try:
            # Get the SSH connection
            ssh_conn = connection_manager.connection_manager.connections[connection.hostname]['ssh_conn']
            
            # Optional: Enter enable mode if requested
            if command_request.enable_mode:
                ssh_conn.enable()
            
            # Execute the command
            output = ssh_conn.send_command(command_request.command)
            
            results.append({
                "hostname": connection.hostname,
                "command": command_request.command,
                "output": output
            })
        
        except Exception as e:
            results.append({
                "hostname": connection.hostname,
                "command": command_request.command,
                "error": f"Command execution error: {str(e)}"
            })
    
    return results


@app.post("/connections/", response_model=schemas.NetworkConnectionResponse)
def create_connection(
    connection: schemas.NetworkConnectionCreate, 
    db: Session = Depends(get_db)
):
    """
    Add a new network device SSH connection
    """
    try:
        new_conn = connection_manager.connection_manager.add_connection(db, connection)
        return new_conn
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/connections/{hostname}")
def remove_connection(
    hostname: str, 
    db: Session = Depends(get_db)
):
    """
    Remove a network device SSH connection
    """
    try:
        connection_manager.connection_manager.remove_connection(db, hostname)
        return {"message": f"Connection to {hostname} removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/connections/", response_model=List[schemas.NetworkConnectionResponse])
def list_connections(db: Session = Depends(get_db)):
    """
    List all network device connections
    """
    connections = db.query(models.NetworkConnection).all()
    return connections

@app.get("/connections/{hostname}/status", response_model=schemas.NetworkConnectionResponse)
def get_connection_status(
    hostname: str, 
    db: Session = Depends(get_db)
):
    """
    Get status of a specific network device connection
    """
    connection = db.query(models.NetworkConnection).filter_by(hostname=hostname).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)