"""Gera os PDFs de fixture do Itaú com dados inventados (nunca a partir dos PDFs reais).

Reproduz o layout das amostras (rótulos, colunas e posições em pontos, A4) para exercitar os
adapters. Rodar a partir de backend/:  python tests/fixtures/itau/make_fixtures.py
"""

from datetime import datetime
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).parent
ROW = 18.5  # extrato: distância entre linhas
TX = 9.0  # fatura: distância entre lançamento e categoria / próximo lançamento


class Doc(FPDF):
    def __init__(self, size: float):
        super().__init__(unit="pt", format="A4")
        self.set_auto_page_break(False)
        self.set_creation_date(datetime(2026, 1, 1))
        self.set_font("Helvetica", size=size)

    def at(self, x: float, y: float, text: str) -> None:
        self.text(x, y, text)

    def right(self, x1: float, y: float, text: str) -> None:
        """Texto alinhado à direita terminando em x1, como os valores dos PDFs do banco."""
        self.text(x1 - self.get_string_width(text), y, text)


# ----------------------------------------------------------------------------- extrato


def extrato(name: str, period: tuple[str, str], pages: list[list[tuple]]) -> None:
    doc = Doc(size=8)
    for index, rows in enumerate(pages):
        doc.add_page()
        y = 60.0
        if index == 0:
            doc.at(260, 72, "FULANO DE TAL 000.000.000-00 agência: 1234 conta: 56789-0")
            doc.at(31, 118, "saldo em conta")
            doc.at(31, 136, "R$ 1.000,00")
            doc.at(28, 176, "extrato conta / lançamentos")
            doc.at(28, 194, f"período de visualização: {period[0]} até {period[1]}")
            doc.at(434, 197, f"emitido em: {period[1]} 10:00:00")
            doc.at(31, 225, "data")
            doc.at(96, 225, "lançamentos")
            doc.at(412, 225, "valor (R$)")
            doc.at(516, 225, "saldo (R$)")
            y = 250.0
        for day, description, value, balance in rows:
            doc.at(31, y, day)
            doc.at(96, y, description)
            if value:
                doc.right(455, y, value)
            if balance:
                doc.right(570, y, balance)
            y += ROW
    doc.at(31, y + 20, "Aviso!")
    doc.at(
        31, y + 32, "Os saldos acima são baseados nas informações disponíveis até esse instante."
    )
    doc.output(str(OUT / name))


EXTRATO_A = [
    [
        ("21/09/2026", "ON Uber UBER 19/09", "-10,93", ""),
        ("21/09/2026", "SALDO DO DIA", "", "1.234,56"),
        ("18/09/2026", "ON Uber UBER 18/09", "-8,94", ""),
        ("18/09/2026", "ON Uber UBER 18/09", "-8,94", ""),
        ("16/09/2026", "PIX AUT HOTMART 16/09", "-1,00", ""),
        ("15/09/2026", "REND PAGO APLIC AUT MAIS", "0,05", ""),
    ],
    [
        ("10/09/2026", "APLICACAO COFRINHOS", "-60,00", ""),
        ("05/09/2026", "PIX TRANSF FULANO05/09", "-1.000,00", ""),
        ("05/09/2026", "PIX TRANSF BELTRAN05/09", "250,00", ""),
        ("02/09/2026", "PAY Uber 02/09", "-26,97", ""),
    ],
]
EXTRATO_B = [
    [
        ("29/09/2026", "APLICACAO COFRINHOS", "-80,00", ""),
        ("25/09/2026", "PIX TRANSF FULANO25/09", "-100,00", ""),
        ("21/09/2026", "ON Uber UBER 19/09", "-10,93", ""),
        ("18/09/2026", "ON Uber UBER 18/09", "-8,94", ""),
        ("18/09/2026", "ON Uber UBER 18/09", "-8,94", ""),
        ("16/09/2026", "PIX AUT HOTMART 16/09", "-1,00", ""),
        ("15/09/2026", "REND PAGO APLIC AUT MAIS", "0,05", ""),
    ],
]

# ----------------------------------------------------------------------------- fatura

LEFT = (149, 176, 337)  # x da data, x da descrição, fim do valor
RIGHT = (365, 392, 553)


def compras(doc: Doc, column: tuple, y: float, rows: list[tuple]) -> float:
    date_x, text_x, value_x1 = column
    for day, description, value, category in rows:
        doc.at(date_x, y, day)
        doc.at(text_x, y, description)
        doc.right(value_x1, y, value)
        y += TX
        if category:
            doc.at(text_x, y, category)
        y += TX
    return y


def section_header(doc: Doc, column: tuple, y: float, title: str, products: bool = False) -> float:
    date_x, text_x, value_x1 = column
    doc.at(date_x, y, title)
    y += 11
    doc.at(date_x, y, "DATA")
    doc.at(text_x, y, "PRODUTOS/SERVIÇOS" if products else "ESTABELECIMENTO")
    doc.right(value_x1, y, "VALOR EM R$")
    return y + 9


def fatura(name: str, total: str) -> None:
    doc = Doc(size=7)

    # Página 1: resumo (nada aqui é lançamento).
    doc.add_page()
    doc.at(40, 60, "FULANO DE TAL")
    doc.at(149, 80, "Resumo da fatura em R$")
    doc.at(149, 95, "Total da fatura anterior 900,00")
    doc.at(149, 110, "Pagamento efetuado em 09/12/2025 - 900,00")
    doc.at(365, 110, "Postagem: 06/01/2026")
    doc.at(356, 125, "L")
    doc.at(365, 125, f"Lançamentos atuais {total}")
    doc.at(365, 140, "Vencimento: 13/01/2026")
    doc.at(365, 155, "Emissão: 06/01/2026")
    doc.at(149, 200, "Banco Itaú S.A. 341-7")

    # Página 2: compras e saques nas duas colunas.
    doc.add_page()
    doc.at(149, 60, "Previsão do próximo fechamento: 06/02/2026.")
    doc.at(149, 85, "Lançamentos: compras e saques")
    doc.at(365, 85, "Lançamentos: compras e saques")
    doc.at(149, 95, "FULANO DE TAL (final 1234)")
    y = section_header(doc, LEFT, 105, "")
    compras(
        doc,
        LEFT,
        y,
        [
            ("15/05", "MERCADOLIVRE*5525309/12", "10,71", "VESTUÁRIO .Osasco"),
            ("15/12", "LOJA EXEMPLO", "120,00", "DIVERSOS .SAO PAULO"),
            ("14/12", "PG *ENJOEI.COM.BR 01/04", "123,46", "DIVERSOS ."),
            ("14/12", "PG *ENJOEI.COM.BR 02/04", "123,46", "DIVERSOS .EMBU DAS ARTE"),
        ],
    )
    compras(
        doc,
        RIGHT,
        95,
        [
            ("14/12", "PG *ENJOEI.COM.BR 03/04", "123,46", "DIVERSOS .EMBU DAS ARTE"),
            ("14/12", "PG *ENJOEI.COM.BR 04/04", "123,46", "DIVERSOS .EMBU DAS ARTE"),
            ("14/12", "PG *ENJOEI.COM.BR ATIV", "- 493,84", "DIVERSOS .EMBU DAS ARTE"),
            ("12/11", "RafolinoPresen", "- 0,06", "VESTUÁRIO .Sao Paulo"),
        ],
    )
    doc.at(528, 495, "Continua...")

    # Página 3: resto das compras, produtos e serviços, totais e próximas faturas (ignoradas).
    doc.add_page()
    doc.at(149, 85, "Lançamentos: compras e saques")
    doc.at(365, 85, "Lançamentos: compras e saques")
    left_y = compras(
        doc,
        LEFT,
        95,
        [
            ("26/11", "SHOPEE *SPECIALSTY03/05", "10,67", "VESTUÁRIO .SAO PAULO"),
            ("26/11", "SHOPEE *SPECIALSTY04/05", "10,67", "VESTUÁRIO .SAO PAULO"),
            ("26/11", "SHOPEE *SPECIALSTY05/05", "10,67", "VESTUÁRIO .SAO PAULO"),
            ("02/01", "NETFLIX.COM", "59,90", "TURISMO E ENTRETENIM.SAO PAULO"),
        ],
    )
    # O ícone "L" do total (coluna direita) fica na mesma altura deste lançamento da esquerda,
    # como na amostra real: a divisa entre colunas não pode colá-lo à linha da esquerda.
    total_y = left_y
    compras(
        doc, LEFT, left_y, [("26/11", "SHOPEE *SPECIALSTY02/05", "10,67", "VESTUÁRIO .SAO PAULO")]
    )
    doc.at(365, 95, "Lançamentos no cartão (final 1234)")
    doc.right(553, 95, "233,23")
    y = section_header(doc, RIGHT, 108, "Lançamentos: produtos e serviços", products=True)
    y = compras(doc, RIGHT, y, [("07/12", "ANUIDADE DIFERENCI02/12", "13,25", "")])
    doc.at(392, y - 9, "Titular 1234")
    doc.at(365, y, "Lançamentos produtos e serviços")
    doc.right(553, y, "13,25")
    doc.at(356, total_y, "L")
    doc.at(365, total_y, "Total dos lançamentos atuais")
    doc.right(553, total_y, total)
    y = section_header(doc, RIGHT, total_y + 20, "Compras parceladas - próximas faturas")
    y = compras(doc, RIGHT, y, [("15/05", "MERCADOLIVRE*5525310/12", "10,71", "")])
    doc.at(365, y, "Próxima fatura")
    doc.right(553, y, "10,71")
    doc.at(528, 495, "Continua...")

    # Página 4: limites e simulações (ignoradas).
    doc.add_page()
    doc.at(40, 60, "Limites de crédito Valor em R$ Simulação Saque Cash")
    doc.at(40, 75, "Valor saque 500,00 99,38 %")
    doc.output(str(OUT / name))


def outro(name: str, lines: list[str]) -> None:
    doc = Doc(size=9)
    doc.add_page()
    for index, line in enumerate(lines):
        doc.at(40, 60 + 14 * index, line)
    doc.output(str(OUT / name))


if __name__ == "__main__":
    extrato("itau_extrato_A.pdf", ("01/09/2026", "21/09/2026"), EXTRATO_A)
    extrato("itau_extrato_B.pdf", ("15/09/2026", "30/09/2026"), EXTRATO_B)
    fatura("itau_fatura_2026-01.pdf", total="246,48")
    fatura("itau_fatura_total_errado.pdf", total="246,49")
    outro("nubank_extrato.pdf", ["NU PAGAMENTOS S.A.", "Extrato de conta", "Saldo final 100,00"])
    outro("desconhecido.pdf", ["Relatório de despesas", "Total 10,00"])
