from flow_manager import FlowManager

fm = FlowManager()
default = fm.get_default_flow()
print('Fluxo padrão:', default)

if default:
    steps = fm.get_flow_steps(default['id'])
    print(f'Etapas do fluxo {default["id"]}:', len(steps))
    
    for i, step in enumerate(steps):
        print(f'- Etapa {i+1}: {step["step_type"]} - {step.get("content", "")[:50]}...')
        print(f'  ID: {step["id"]}, Ordem: {step.get("step_order", "N/A")}')
        if step.get('media_url'):
            print(f'  Mídia: {step["media_url"]}')
        print(f'  Botões: {len(step.get("buttons", []))}')
        print()
else:
    print('Nenhum fluxo padrão encontrado') 