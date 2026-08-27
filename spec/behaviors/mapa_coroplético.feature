# language: pt

Funcionalidade: Mapa Coroplético Interativo
  Como um profissional de saúde do Sudoeste do Paraná
  Quero visualizar um mapa colorido com dados de internações
  Para identificar padrões de utilização dos serviços de saúde por município

  Cenário: Exibição inicial do mapa
    Dado que o usuário acessa o sistema Longevus
    Quando o mapa é carregado
    Então os municípios do Sudoeste do Paraná devem ser renderizados
    E todos os municípios devem estar coloridos com a escala padrão

  Cenário: Aplicação de filtro por CID e sexo
    Dado que o usuário seleciona o capítulo CID "X" (Doenças respiratórias)
    E seleciona o sexo "Masculino"
    Quando clica em "Atualizar Mapa"
    Então o mapa deve atualizar em menos de 2 segundos
    E os municípios devem ser coloridos conforme a taxa de internações por 100 mil habitantes
    E municípios com maior taxa devem aparecer em vermelho
    E municípios com menor taxa devem aparecer em amarelo

  Cenário: Coloração normalizada pela população
    Dado que o município "Pato Branco" tem 91.836 habitantes e 7.895 internações
    E o município "Verê" tem 7.932 habitantes e 1.056 internações
    Quando o mapa é colorido
    Então "Verê" deve receber uma cor mais intensa que "Pato Branco"
    Porque a taxa de "Verê" é maior, ainda que seu número absoluto seja menor
    E o mapa não deve reproduzir a distribuição populacional da região

  Cenário: Cortes da escala por quintis da distribuição
    Dado que as taxas observadas no conjunto filtrado vão de 5.476 a 13.313 por 100 mil habitantes
    Quando o mapa é colorido
    Então os cortes da escala devem ser os quintis dessa distribuição
    E cada um dos cinco níveis de cor deve receber aproximadamente um quinto dos municípios
    E nenhum nível da escala deve permanecer sem uso
    Porque cortes proporcionais ao máximo concentrariam quase todos os municípios nos níveis superiores

  Cenário: Município sem população cadastrada
    Dado que um município do recorte não possui população cadastrada
    Quando o mapa é colorido
    Então esse município deve receber a cor neutra de "sem dados"
    E não deve ser omitido da malha

  Cenário: Tooltip ao passar o mouse
    Dado que o mapa está renderizado com dados
    Quando o usuário passa o mouse sobre um município
    Então deve aparecer um tooltip com:
      | Campo               | Exemplo               |
      | Nome do município   | Francisco Beltrão     |
      | Taxa de internação  | 10.065,6 / 100 mil hab. |
      | Atendimentos        | 9.730                 |
      | População           | 96.666                |
      | Valor total         | R$ 14.293.187,45      |

  Cenário: Nenhum resultado para os filtros
    Dado que o usuário seleciona filtros sem registros correspondentes
    Quando clica em "Atualizar Mapa"
    Então todos os municípios devem aparecer sem coloração
    E uma mensagem "Nenhum dado encontrado para os filtros selecionados" deve ser exibida
