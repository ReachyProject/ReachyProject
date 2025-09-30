import time
from dotenv import load_dotenv
import os
#from rich import print

# Load environment variables
load_dotenv()

def main():
    print("[bold cyan]" + "=" * 50 + "[/bold cyan]")
    print("[bold green]Reachy Service Starting...[/bold green]")
    print("[bold cyan]" + "=" * 50 + "[/bold cyan]")
    
    # Load configuration
    persona = os.getenv('PERSONA', 'Not Set')
    age_range = os.getenv('AGE_RANGE', 'Not Set')
    mood = os.getenv('MOOD', 'Not Set')
    llm_provider = os.getenv('LLM_PROVIDER', 'Not Set')
    llm_model = os.getenv('LLM_MODEL', 'Not Set')
    
    print("\n[bold yellow]Configuration Loaded:[/bold yellow]")
    print(f"  [cyan]- Persona:[/cyan] {persona}")
    print(f"  [cyan]- Age Range:[/cyan] {age_range}")
    print(f"  [cyan]- Mood:[/cyan] {mood}")
    print(f"  [cyan]- LLM Provider:[/cyan] {llm_provider}")
    print(f"  [cyan]- LLM Model:[/cyan] {llm_model}")
    print()
    
    # Simulate service running
    counter = 0
    try:
        while True:
            counter += 1
            print(f"[dim]Service running... (iteration {counter})[/dim]")
            
            # Simulate different types of logs
            if counter % 5 == 0:
                print(f"  [blue]→[/blue] Processing request with [bold]{persona}[/bold] persona")
            
            if counter % 10 == 0:
                print(f"  [blue]→[/blue] Using [bold]{llm_model}[/bold] model from [bold]{llm_provider}[/bold]")
            
            if counter % 15 == 0:
                print(f"  [green]✓[/green] Mood set to: [bold]{mood}[/bold]")
            
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n[bold cyan]" + "=" * 50 + "[/bold cyan]")
        print("[bold red]Service stopped by user[/bold red]")
        print("[bold cyan]" + "=" * 50 + "[/bold cyan]")
    except Exception as e:
        print(f"\n[bold red]ERROR:[/bold red] {str(e)}")
        raise

if __name__ == "__main__":
    main()