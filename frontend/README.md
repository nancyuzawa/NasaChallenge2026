# Frontend Firewatch

Protótipo de dashboard feito com Python e Streamlit, com telas de mapa, atividade e relatórios.

## Executar localmente

Na raiz do projeto, execute:

```powershell
python run.py
```

No Windows também é possível abrir `iniciar.cmd` com dois cliques.
O iniciador cria `frontend/.venv` se necessário, instala os pacotes de
`requirements.txt` e executa o Streamlit com o mesmo Python. Não é preciso
ativar o ambiente nem alterar a política de execução do PowerShell.
A instalação usa os certificados confiáveis do Windows para validar HTTPS.

Para conferir as importações e a compatibilidade das dependências:

```powershell
python run.py --check
```

Para instalar alterações em `requirements.txt`, basta executar o iniciador
novamente. Para solicitar a instalação explicitamente, use `python run.py --install`.
Declare nesse arquivo cada nova biblioteca externa usada pelo frontend.

## VS Code

Abra a pasta raiz `NasaChallenge2026`. Use F5 com a configuração
`Firewatch: iniciar Streamlit`. O projeto já aponta para o Python de
`frontend/.venv/Scripts/python.exe`.
Se o VS Code já tinha outro interpretador selecionado, escolha esse caminho
em **Python: Select Interpreter**. A execução direta de `frontend/app.py`
também redireciona para o iniciador e usa o ambiente do projeto.

O painel inclui filtros de país, estado/província, latitude, longitude e intervalo de datas. Os indicadores, a série histórica e os pontos do mapa são demonstrativos e estão em `data.py`; podem ser substituídos pela integração com a API quando o backend estiver pronto.

O dashboard segue `midias/prototype/1. Dashboard.png`, com período inicial de
janeiro a dezembro de 2025. A barra lateral mantém os acessos a mapa, atividade
e relatórios. A lupa permite selecionar cidades de referência e **Filter** abre
os filtros de região, coordenadas e período. **Reset** restaura Campinas e 2025.

O globo WebGL permite girar a Terra e clicar em países e cidades. O seletor
sobre o mapa lista as cidades de referência do país selecionado. Essas ações
atualizam o mesmo filtro de localização usado por **Search** e **Filter**,
preservando o intervalo de datas. O catálogo é local e não inclui todas as cidades.

Os indicadores e o gráfico usam amostras sintéticas por cidade, exclusivamente
para 2025. A soma das cidades disponíveis forma a amostra de cada país; não é
uma estimativa nacional. Intervalos fora de 2025 e áreas sem amostras exibem zero.
Os dados não são medições de satélite. As páginas de atividade e relatórios
compartilham a seleção. A conexão com o backend ainda não está implementada.

A implementação do mapa, os dados geográficos e as dependências JavaScript
estão em `components/globe`; consulte seu README para fontes e licença.
Os estilos compartilhados ficam em `styles.css`. O dashboard distribui mapa,
indicadores e gráfico pela altura disponível da janela, sem rolagem da página.
Fontes, ícones e espaçamentos acompanham o tamanho da tela. Em janelas estreitas,
o mapa fica acima dos indicadores, mantendo todos os painéis visíveis.
O logo da barra lateral é carregado de `midias/logo/Logo.svg`.
O frontend utiliza os recursos de layout do Streamlit 1.67+.
