#!/usr/bin/env python3
"""
Script para verificar se o ffmpeg e as bibliotecas de vídeo estão instalados corretamente
"""

import subprocess
import sys

def check_ffmpeg():
    """Verifica se o ffmpeg está instalado"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ ffmpeg está instalado e funcionando")
            # Mostrar versão
            version_line = result.stdout.split('\n')[0]
            print(f"   Versão: {version_line}")
            return True
        else:
            print("❌ ffmpeg não está funcionando corretamente")
            return False
    except FileNotFoundError:
        print("❌ ffmpeg não está instalado")
        return False
    except Exception as e:
        print(f"❌ Erro ao verificar ffmpeg: {e}")
        return False

def check_python_libs():
    """Verifica se as bibliotecas Python estão instaladas"""
    libs_to_check = [
        ('cv2', 'OpenCV'),
        ('moviepy', 'MoviePy'),
        ('numpy', 'NumPy')
    ]
    
    all_ok = True
    for lib_name, display_name in libs_to_check:
        try:
            __import__(lib_name)
            print(f"✅ {display_name} está instalado")
        except ImportError as e:
            print(f"❌ {display_name} não está instalado: {e}")
            all_ok = False
    
    return all_ok

def test_moviepy_import():
    """Testa se o MoviePy consegue importar corretamente"""
    try:
        from moviepy.editor import VideoFileClip
        print("✅ MoviePy consegue importar VideoFileClip")
        return True
    except ImportError as e:
        print(f"❌ Erro ao importar MoviePy: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado com MoviePy: {e}")
        return False

def main():
    """Função principal"""
    print("🔍 Verificando instalação do ffmpeg e bibliotecas de vídeo")
    print("=" * 60)
    
    # Verificar ffmpeg
    ffmpeg_ok = check_ffmpeg()
    
    print("\n" + "-" * 40)
    
    # Verificar bibliotecas Python
    libs_ok = check_python_libs()
    
    print("\n" + "-" * 40)
    
    # Testar MoviePy
    moviepy_ok = test_moviepy_import()
    
    print("\n" + "=" * 60)
    print("📊 RESUMO:")
    
    if ffmpeg_ok and libs_ok and moviepy_ok:
        print("🎉 Tudo está funcionando corretamente!")
        print("✅ Conversão de vídeo para video note deve funcionar")
    else:
        print("⚠️  Alguns componentes não estão funcionando:")
        if not ffmpeg_ok:
            print("   - ffmpeg precisa ser instalado")
        if not libs_ok:
            print("   - Bibliotecas Python precisam ser instaladas")
        if not moviepy_ok:
            print("   - MoviePy tem problemas de importação")
        
        print("\n🔧 SOLUÇÕES:")
        print("1. Instale o ffmpeg no sistema")
        print("2. Execute: pip install -r requirements.txt")
        print("3. Para Railway, use o arquivo nixpacks.toml criado")

if __name__ == "__main__":
    main() 