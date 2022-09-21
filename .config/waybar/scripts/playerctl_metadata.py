import re
import subprocess


def main():
    metadata = {}
    metadata['title'] = subprocess.run(['playerctl', 'metadata', '--format',
                                        '"{{title}}"'], capture_output=True, text=True).stdout.strip().strip('"')
    metadata['album'] = subprocess.run(['playerctl', 'metadata', '--format',
                                        '"{{album}}"'], capture_output=True, text=True).stdout.strip().strip('"')
    metadata['artist'] = subprocess.run(['playerctl', 'metadata', '--format',
                                        '"{{artist}}"'], capture_output=True, text=True).stdout.strip().strip('"')
    metadata['status'] = subprocess.run(
        ['playerctl', 'status'], capture_output=True, text=True).stdout.strip().strip('"')
    # print(metadata)

    icons = {
        'Playing': '',
        'Paused': '',
        'Stopped': ''
    }

    youtube_title = re.search('(?<=\) ).*', metadata['title'])
    title = youtube_title.group().strip(
    ) if youtube_title != None else metadata['title']

    output_string = f'{icons[metadata["status"]]}  {title} {metadata["artist"]}'
    print(output_string)
    return output_string


main()
