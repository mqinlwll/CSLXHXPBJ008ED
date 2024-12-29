import os
import re
from collections import defaultdict
from mutagen import File
from mutagen.mp4 import MP4  # Add MP4 support for AAC and ALAC
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup


def parse_metadata(music_folder):
    music_data = defaultdict(lambda: defaultdict(list))
    track_metadata = []
    album_artists = defaultdict(set)

    for root, _, files in os.walk(music_folder):
        for file in files:
            if file.endswith(('.mp3', '.flac', '.wav', '.m4a')):
                filepath = os.path.join(root, file)
                audio = File(filepath, easy=True)

                if not audio:
                    continue

                title = audio.get('title', [os.path.splitext(file)[0]])[0]
                artist = audio.get('artist', ['Unknown Artist'])[0]
                album = audio.get('album', ['Unknown Album'])[0]
                album_artist = audio.get('albumartist', ['Unknown Album Artist'])[0]
                bitrate = audio.info.bitrate // 1000 if hasattr(audio.info, 'bitrate') else 'N/A'
                sample_rate = audio.info.sample_rate if hasattr(audio.info, 'sample_rate') else 'N/A'
                duration = audio.info.length if hasattr(audio.info, 'length') else 0
                codec = determine_codec(audio)
                file_size = os.path.getsize(filepath)

                file_size_str = (
                    f"{file_size / (1024 ** 3):.2f} GB"
                    if file_size > 1024 ** 3
                    else f"{file_size / (1024 ** 2):.2f} MB"
                )

                hours, remainder = divmod(duration, 3600)
                minutes, seconds = divmod(remainder, 60)
                duration_str = (
                    f"{int(hours)}:{int(minutes):02}:{int(seconds):02}"
                    if hours > 0
                    else f"{int(minutes)}:{int(seconds):02}"
                )

                channels = "Stereo" if hasattr(audio.info, 'channels') and audio.info.channels > 1 else "Mono"

                track_data = {
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "album_artist": album_artist,
                    "bitrate": f"{bitrate} kbps",
                    "sample_rate": f"{sample_rate} Hz",
                    "duration": duration_str,
                    "codec": codec,
                    "file_size": file_size_str,
                    "channels": channels
                }

                album_artists[album].add(artist)

                if track_data not in music_data[artist][album]:
                    track_metadata.append(track_data)
                    music_data[artist][album].append(track_data)

    for artist, albums in music_data.items():
        for album, tracks in albums.items():
            if len(album_artists[album]) > 1 or "Various Artists" in album_artists[album]:
                for track in tracks:
                    track['album_artist'] = "Various Artists"

    return music_data, track_metadata


def determine_codec(audio):
    """
    Determines the codec used by the audio file.
    """
    if isinstance(audio, MP4) and hasattr(audio.info, 'codec'):
        # Recognize AAC and ALAC
        codec_map = {
            'alac': 'ALAC',
            'mp4a': 'AAC',
        }
        return codec_map.get(audio.info.codec, "Unknown Codec")
    return type(audio).__name__


def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def generate_dashboard(music_data, output_folder):
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['sanitize_filename'] = sanitize_filename

    os.makedirs(output_folder, exist_ok=True)

    index_template = env.get_template('index.html')
    artist_template = env.get_template('artist.html')
    album_template = env.get_template('album.html')
    track_template = env.get_template('track.html')

    index_file_path = os.path.join(output_folder, 'index.html')
    existing_artist_links = set()

    # Check if index.html already exists
    if os.path.exists(index_file_path):
        with open(index_file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')

        # Extract existing artist links to avoid duplicates
        for card in soup.find_all('div', class_='card'):
            link = card.find('a')
            if link and link['href']:
                existing_artist_links.add(link['href'])
    else:
        soup = BeautifulSoup("<div class='grid'></div>", 'html.parser')

    grid_div = soup.find('div', class_='grid')

    # Generate artist cards only if they are not already present
    for artist in music_data.keys():
        artist_link = f"{sanitize_filename(artist)}/index.html"
        if artist_link not in existing_artist_links:
            new_card = soup.new_tag('div', attrs={'class': 'card'})
            new_link = soup.new_tag('a', href=artist_link)
            new_link.string = artist
            new_card.append(new_link)
            grid_div.append(new_card)

    # Render the full index template with the grid of artist cards
    final_html = index_template.render(artists=[{
        'link': sanitize_filename(artist),
        'name': artist
    } for artist in music_data.keys()])

    # Write the final HTML with the artist cards embedded
    with open(index_file_path, 'w', encoding='utf-8') as f:
        f.write(final_html)

    # Generate artist and album pages
    for artist, albums in music_data.items():
        artist_folder = os.path.join(output_folder, sanitize_filename(artist))
        os.makedirs(artist_folder, exist_ok=True)

        artist_html = artist_template.render(artist=artist, albums=[
            {"name": album, "link": sanitize_filename(album), "track_count": len(songs)}
            for album, songs in albums.items()
        ])
        with open(os.path.join(artist_folder, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(artist_html)

        for album, songs in albums.items():
            album_folder = os.path.join(artist_folder, sanitize_filename(album))
            os.makedirs(album_folder, exist_ok=True)

            album_html = album_template.render(
                artist=artist,
                album=album,
                songs=songs,
                track_count=len(songs)
            )
            with open(os.path.join(album_folder, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(album_html)

            # Generate track detail pages
            for song in songs:
                track_filename = sanitize_filename(song["title"]) + ".html"
                track_html = track_template.render(
                    title=song["title"],
                    artist=song["artist"],
                    album=song["album"],
                    album_artist=song["album_artist"],
                    bitrate=song["bitrate"],
                    sample_rate=song["sample_rate"],
                    duration=song["duration"],
                    codec=song["codec"],
                    file_size=song["file_size"],
                    channels=song["channels"]
                )
                with open(os.path.join(album_folder, track_filename), 'w', encoding='utf-8') as f:
                    f.write(track_html)


def main():
    music_folder = input("Enter the path to your music folder: ")
    output_folder = "output_dashboard"

    music_data, track_metadata = parse_metadata(music_folder)
    generate_dashboard(music_data, output_folder)

    print(f"Dashboard generated in {output_folder} folder.")


if __name__ == '__main__':
    main()

