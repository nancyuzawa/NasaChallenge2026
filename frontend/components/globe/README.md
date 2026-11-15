# Globo de seleção de localização

Componente Streamlit v1 com comunicação bidirecional. O globo envia somente
identificadores de países/cidades e um identificador de evento. O Python valida
os identificadores no catálogo local antes de atualizar os filtros da sessão.
Os arquivos de renderização e os dados geográficos são servidos localmente;
o componente não usa CDN, geocodificação externa ou chave de API em execução.

- Renderizador: [Globe.gl](https://globe.gl/) **2.46.2**, pacote npm verificado
  pelo SHA-512 publicado no registro. Bundle em `vendor/globe.gl.min.js` e
  licença MIT em `vendor/globe.gl.LICENSE`.
- Limites de países: [Natural Earth, admin 0, 110m](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson).
- Cidades de referência: [Natural Earth, populated places, 110m](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_populated_places.geojson),
  complementadas pelas cidades brasileiras já disponíveis no protótipo.
- Os catálogos contêm somente os campos usados pela aplicação.

Arraste para girar. Clique no território de um país para filtrar o país inteiro;
clique em um ponto ou use o seletor de cidades para filtrar uma cidade disponível.
As teclas de seta giram o globo, `+`/`-` controlam o zoom, e o primeiro botão
retorna à localização selecionada. O botão de expansão usa a API de tela cheia
ou ocupa a janela do aplicativo quando essa API não está disponível.

Requer WebGL. Se o navegador não conseguir inicializá-lo, o componente mostra
uma mensagem e os filtros Search/Filter continuam disponíveis.
