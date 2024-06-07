import subprocess
import json

def main():
    result = subprocess.run(['lsdev', '-jdHmtTsfcp'], stdout=subprocess.PIPE)

    json_data = json.loads(result.stdout)

    disks = []

    for row in json_data['rows']:
        for disk in row:
            if not disk['occupied']:
                continue

            device_path = disk['dev']

            disks.append({
                'name': disk['bay-id'],
                'capacity': disk['capacity'],
                'model': disk['model-name'],
                'type': disk['disk_type'],
                'health': disk['health'],
                'phy_path': disk['dev-by-path'],
                'sd_path': device_path,
                'vdev_path': f'/dev/disk/by-vdev/{disk["bay-id"]}',
                'serial': disk['serial'],
                'temp': disk['temp-c'],
            })

    print(json.dumps(disks, indent=4))

if __name__ == '__main__':
    main()
