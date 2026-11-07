#!/usr/bin/env python3
"""Download every video/photo original from a public iCloud shared-album link.

Usage: python3 icloud_download.py https://share.icloud.com/photos/<token> OUT_DIR
Hosts needed: ckdatabasews.icloud.com, p<NN>-ckdatabasews.icloud.com (printed if blocked),
cvws.icloud-content.com / cvws-h2.icloud-content.com.
"""
import base64, json, os, sys, urllib.parse, urllib.request

def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))

def main(link, out):
    token = link.rstrip("/").split("/")[-1].split("#")[0]
    r = post("https://ckdatabasews.icloud.com/database/1/com.apple.photos.cloud/production/public/records/resolve",
             {"shortGUIDs": [{"value": token}]})["results"][0]
    acc = r["anonymousPublicAccess"]
    part = acc["databasePartition"].replace(":443", "")
    print("partition host:", part)
    z = {"zoneName": r["zoneID"]["zoneName"], "ownerRecordName": r["zoneID"]["ownerRecordName"]}
    base = f"{part}/database/1/com.apple.photos.cloud/production/shared"
    q = "?publicAccessAuthToken=" + urllib.parse.quote(acc["token"])
    ch = post(f"{base}/changes/zone{q}", {"zones": [{"zoneID": z, "desiredKeys": None}]})
    os.makedirs(out, exist_ok=True)
    for rec in ch["zones"][0].get("records", []):
        if rec["recordType"] != "CPLMaster":
            continue
        f = rec["fields"]
        name = base64.b64decode(f["filenameEnc"]["value"]).decode() if "filenameEnc" in f else rec["recordName"] + ".bin"
        url = f["resOriginalRes"]["value"]["downloadURL"].replace("${f}", name)
        dest = os.path.join(out, name)
        print("downloading", name, "from", urllib.parse.urlparse(url).netloc)
        urllib.request.urlretrieve(url, dest)
        print("  ->", dest, os.path.getsize(dest), "bytes")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
