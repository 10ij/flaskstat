# I've tried my best to keep this nicely commented

import os
import time
import glob
import logging
from flask import Flask, jsonify, render_template, redirect, url_for, session
import functools
from datetime import timedelta

app = Flask(__name__)

# Mounts for the resource commands

HOST_PROC = '/host/proc'
HOST_ROOT = '/host/root'
TOP_N_PROCS = 10

# OAuth / Session Setup

app.secret_key = os.getenv('SECRET_KEY')
from authlib.integrations.flask_client import OAuth
app.permanent_session_lifetime = timedelta(minutes=5)

@app.before_request
def make_session_permanent():
    session.permanent = True

oauth = OAuth(app)

OIDC_Name = os.getenv('OIDC_PROVIDER_NAME') # I'm aware this wasn't needed

pocket_id = oauth.register(
    name=OIDC_Name,
    client_id=os.getenv('OIDC_CLIENT_ID'),
    client_secret=os.getenv('OIDC_CLIENT_SECRET'),
    server_metadata_url=os.getenv('OIDC_SERVER_METADATA_URL')
)

# Helper Functions 

def read_mem():
    try:
        meminfo = {}
        with open(os.path.join(HOST_PROC, 'meminfo')) as f:
            for line in f:
                key, val = line.split(':')
                meminfo[key.strip()] = int(''.join(filter(str.isdigit, val)))
        total = meminfo['MemTotal']
        available = meminfo['MemAvailable']
        used = total - available
        return {"total_mb": round(total/1024, 1), "used_mb": round(used/1024, 1), "pct": round(used/total*100, 1)}
    except Exception as e:
        logging.error(f"Memory read failed: {e}")
        return {"total_mb": 0, "used_mb": 0, "pct": 0}

def read_cpu():
    def parse_stat():
        with open(os.path.join(HOST_PROC, 'stat')) as f:
            line = f.readline()
            parts = line.strip().split()[1:]
            return list(map(int, parts))
    try:
        a = parse_stat()
        time.sleep(0.2)
        b = parse_stat()
        diff = [b[i]-a[i] for i in range(len(a))]
        total = sum(diff)
        idle = diff[3] + diff[4]
        pct = round(100*(1 - idle/total),1)
        return {"pct": pct}
    except Exception as e:
        logging.error(f"CPU read failed: {e}")
        return {"pct":0}

def read_disk():
    paths = ["/", "/mnt/data"]
    disks = {}
    for p in paths:
        full_path = os.path.join(HOST_ROOT, p.lstrip("/"))
        if not os.path.exists(full_path):
            logging.warning(f"Disk path {full_path} not found, skipping.")
            disks[p] = {"used_pct": None, "exists": False}
            continue
        try:
            st = os.statvfs(full_path)
            total = st.f_blocks * st.f_frsize
            free  = st.f_bfree * st.f_frsize
            disks[p] = {"used_pct": round(100*(1 - free/total),1), "exists": True}
        except Exception as e:
            logging.error(f"Disk read failed for {full_path}: {e}")
            disks[p] = {"used_pct": None, "exists": True}
    return disks

def read_procs(limit=TOP_N_PROCS):
    procs = []
    for stat_file in glob.glob(os.path.join(HOST_PROC,'[0-9]*/stat')):
        try:
            with open(stat_file) as f:
                data = f.read().split()
                pid = int(data[0])
                name = data[1].strip('()')
                rss = int(data[23])*4/1024
                procs.append({"pid":pid,"name":name,"rss_mb":round(rss,1)})
        except Exception:
            continue
    procs.sort(key=lambda x: x['rss_mb'], reverse=True)
    logging.info(f"Top {limit} processes read, total processes found: {len(procs)}")
    return procs[:limit]

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user' not in session:
            return redirect(url_for('index'))
        return view(**kwargs)
    return wrapped_view

def api(view): # Just the above with a json response. Easiest method
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return view(**kwargs)
    return wrapped_view

# Routes

@app.route('/login') # Should just redir to your OIDC Provider
def login():
    redirect_uri = url_for('authorize', _external=True, _scheme='https')
    return pocket_id.authorize_redirect(redirect_uri, scope=['openid', 'profile', 'email'])

@app.route('/callback') # Just a simple callback for your OIDC Provider to use
def authorize():
    token = pocket_id.authorize_access_token()
    resp = pocket_id.get(pocket_id.server_metadata['userinfo_endpoint'], token=token)
    session['user'] = resp.json() # Creates the session
    return redirect(url_for('new_view'))

@app.route("/view") # Main dashboard
@login_required # Making sure only the right people see the dash
def new_view():
    stats = {
        "cpu": read_cpu(),
        "memory": read_mem(),
        "disk": read_disk(),
        "top_processes": read_procs()
    }
    return render_template("dash.html", stats=stats)

@app.route("/") # Just the login page
def index():
    if 'user' not in session:
        return render_template("login.html", current_year=time.localtime().tm_year, name=OIDC_Name)
    else:
        return redirect(url_for('new_view'))

@app.route('/logout') # Self explanitory
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route("/api/stats") # For the html/js stats pull
@api
def api_stats():
    stats = {
        "cpu": read_cpu(),
        "memory": read_mem(),
        "disk": read_disk(),
        "top_processes": read_procs()
    }
    return jsonify(stats)

# Main
if __name__ == "__main__":
    logging.info("Starting host monitor on 0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
