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
                'vdev_path': f'/dev/disk/by-vdev/{disk["bay-id"]}',
                'phy_path': disk['dev-by-path'],
                'sd_path': device_path,
                'name': disk['bay-id'],
                'model': disk['model-name'],
                'serial': disk['serial'],
                'capacity': disk['capacity'],
                'type': disk['disk_type'],
                'usable': True,
                'temp': disk['temp-c'],
                'health': disk['health'],
                'rotation_rate': disk['rotation-rate'],
                'power_on_count': disk['power-cycle-count'],
                'power_on_time': disk['power-on-time'],
            })

    print(json.dumps(disks, indent=4))

if __name__ == '__main__':
    main()
