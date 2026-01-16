import loader
import argparse
from menu import menu
from repository import rep
from loader import PluginInterface
from sys import exit
from video_player import play_video
from json import load, dump
from manga_tupi import main as manga_tupi
from os import name
from pathlib import Path
import shutil
import subprocess
import requests
import ui_system


HISTORY_PATH = Path.home().as_posix() + "/.local/state/ani-tupi/" if name != 'nt' else "C:\\Program Files\\ani-tupi\\"

def main(args):
    loader.load_plugins({"pt-br"}, None)

    if not args.continue_watching:
        query = ui_system.create_prompt("Nome do anime", "Digite o nome do anime e pressione Enter.") if args.anime == None else args.anime   
        rep.search_anime(query, args.debug)
        titles = rep.get_anime_titles()
        selected_anime = ui_system.create_fzf_menu(titles, msg="Escolha o Anime: ")

        selected_anime = selected_anime.split(" - ")[0]

        rep.search_episodes(selected_anime)
        episode_list = rep.get_episode_list(selected_anime)
        
        if not args.download:
            selected_episode = ui_system.create_fzf_menu(episode_list, msg="Escolha o episódio: ")
            episode_idx = episode_list.index(selected_episode) 
    else:
        selected_anime, episode_idx = load_history()
    
    num_episodes = len(rep.anime_episodes_urls[selected_anime][0][0])
    
    if args.download:
        return download_anime(selected_anime, rep.anime_episodes_urls[selected_anime][0][0], args.range, args.debug)
    while True:
        episode = episode_idx + 1
        player_url = rep.search_player(selected_anime, episode)
        if args.debug: print(player_url)
        play_video(player_url, args.debug)
        save_history(selected_anime, episode_idx)

        opts = []
        if episode_idx < num_episodes - 1:
            opts.append("Próximo")
        if episode_idx > 0:
            opts.append("Anterior")

        selected_opt = ui_system.create_fzf_menu(opts, msg="O que quer fazer agora? > ")

        if selected_opt == "Próximo":
            episode_idx += 1 
        elif selected_opt == "Anterior":
            episode_idx -= 1

def download_anime(selected_anime,episode_list,download_range, debug):
    if debug: ui_system.print_log(f"Verificando uso de Range: {download_range}", "DEBUG", "gray")
    if download_range:
        if debug: ui_system.print_log(f"Aplicando range {download_range}", "DEBUG", "gray")
        episode_list = filter_list_based_in_rangetype(download_range,episode_list)
        if debug: ui_system.print_log(f"nova lista de episódios: {episode_list}", "DEBUG", "gray")


    videos_path = ui_system.create_prompt("Diretório do episódio", "Determine o diretório raíz para o episódio (padrão: ~/Videos/)")
    videos_path = Path(videos_path).expanduser() if videos_path != ""  else Path("~/Videos/").expanduser()

    if debug: ui_system.print_log(f"Arquivo raíz: {videos_path.as_posix()}", "DEBUG", "gray")

    if not videos_path.is_dir():
        ui_system.print_log("Não é uma pasta, usando diretório padrão", "WARN", "yellow")
        videos_path = Path.home() / "Videos"

    anime_path = videos_path / selected_anime
    if debug: ui_system.print_log(f"Criando pasta '{anime_path.as_posix()}'", "DEBUG", "gray")

    if anime_path.is_dir():
        choice = ui_system.create_prompt("Anime já baixado", "O anime possívelmente já foi baixado, deseja *excluir* a pasta ou *parar* o processo?")

        if choice.lower() == "excluir":
            shutil.rmtree(anime_path.as_posix())
        elif choice.lower() == "parar":
            raise KeyboardInterrupt()
        else:
            raise KeyboardInterrupt()

    anime_path.mkdir()

    for i,episode in enumerate(episode_list,start=1):
        ui_system.print_log(f"baixando episódio {i}", "INFO", "white")
        player_url = rep.search_player(selected_anime, i)

        download_episode(player_url, anime_path, f"Episódio {i}", debug)

def download_episode(player_url, anime_path, name, debug):
    episode_path = anime_path / (name + ".mp4")
    # verificar o tipo do link (stream ou vídeo)
    if debug: ui_system.print_log(f"Fazendo request em {player_url}", "DEBUG", "gray")
    response = requests.get(player_url)
    content_type = response.headers.get("content-type")
    if debug: ui_system.print_log(f"Content-Type: {content_type.split(';')}", "DEBUG", "gray")
    try:
        if not content_type.split(";")[0] == "video/mp4":
            if debug: ui_system.print_log(f"Processando com yt_dlp", "DEBUG", "gray")
            process = subprocess.run([
            "yt-dlp", 
            "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]", 
            player_url, 
            "--output", episode_path.as_posix()
            ])
            process.check_returncode()
        else:
            if debug: ui_system.print_log(f"Processando com FFmpeg", "DEBUG", "gray")
            process =subprocess.run([
            "ffmpeg",
            "-i", player_url,
            "-c", "copy",
            episode_path.as_posix()
            ])
            process.check_returncode()
    except FileNotFoundError:
        ui_system.print_log("FFmpeg e yt_dlp não encontrados no $PATH, você baixou eles?", "ERRO", "red")
    except subprocess.CalledProcessError:
        ui_system.print_log("Houve um erro durante o processo de download do episódio", "ERRO", "red")
        decide = input("Deseja abortar o programa? (S/n)")
        exit(1) if not decide.lower() == "n" else None 

def load_history():
    file_path = HISTORY_PATH + "history.json"
    try:
        with open(file_path, "r") as f:
            data = load(f)
            titles = dict()
            for entry, info in data.items():
                ep_info = f" (Ultimo episódio assistido {info[1] + 1})"
                titles[entry + ep_info] = len(ep_info)
            selected = ui_system.create_fzf_menu(list(titles.keys()), msg="Continue assistindo.")
            anime = selected[:-titles[selected]]
            episode_idx = data[anime][1]
            rep.anime_episodes_urls[anime] = data[anime][0]
        return anime, episode_idx
    except FileNotFoundError:
        print("Sem histórico de animes")
        exit()
    except PermissionError:
        print("Sem permissão para ler arquivos.")
        return

def save_history(anime, episode):
    file_path = HISTORY_PATH + "history.json"
    try:
        with open(file_path, "r+") as f:
            data = load(f)
            data[anime] = [rep.anime_episodes_urls[anime],
                           episode]
        with open(file_path , "w") as f:
            dump(data, f)

    except FileNotFoundError:
        Path(file_path).mkdir(parents=True, exist_ok=True)

        with open(file_path, "w") as f:
            data = dict()
            data[anime] = [rep.anime_episodes_urls[anime],
                            episode]
            dump(data, f)

    except PermissionError:
        print("Não há permissão para criar arquivos.")
        return

def to_rangetype(rangestr):
    range_list = rangestr.split("-")
    return [int(range_list[0]),int(range_list[1])]

def filter_list_based_in_rangetype(rangetype,x_list):
    return [episode for x, episode in enumerate(x_list,start=0) if rangetype[0]-1 <= x <= rangetype[1]-1]

def recognize_rangetype(rangestr):
    range_list = rangestr.split("-")
    try:
        min_val = int(range_list[0])
        max_val = int(range_list[1])
        if min_val > max_val:
            raise Exception("Valor mínimo maior que o máximo!")
    except Exception:
        raise argparse.ArgumentTypeError("Range está incorreto. O certo é 'começo-fim' (exemplo: '10-20', '1-12', etc)")

    return to_rangetype(rangestr)

if __name__=="__main__":
    parser = argparse.ArgumentParser(
                prog = "ani-tupi",
                description="Veja anime sem sair do terminal.",
            )
    parser.add_argument("--debug", action="store_true", help="Modo de desenvolvedores")
    parser.add_argument("--continue_watching", "-c", action="store_true", help="Continuar assistindo")
    parser.add_argument("--manga", "-m", action="store_true", help="Usa o manga_tupi para abrir mangás")
    parser.add_argument("anime", type=str, nargs="?", help="nome do anime com aspas")
    parser.add_argument("--download", "-d", action="store_true", help="Ativa modo de download")
    parser.add_argument("--range", "-r", type=recognize_rangetype, help="Intervalos de episódios a serem baixados ('1-10', '5-12', etc)")
    args = parser.parse_args()
    
    if args.debug:ui_system.print_log(f"Argumentos: {str(args)}", "DEBUG", "gray")

    try: 
        if args.manga:
            manga_tupi()
        else:
            main(args)
    except KeyboardInterrupt:
        ui_system.console.print()
        ui_system.print_log("Interrompido pelo usuário. Abortando...", "ABORT", "red")
        exit(0)
     
