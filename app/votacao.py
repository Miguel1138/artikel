"""Votação suave entre ramos do classificador de intenções.

Cada ramo é um pipeline completo (vetorizador + regressão logística) que recebe texto bruto
e devolve probabilidades; a decisão é a média ponderada delas. O ramo de n-gramas acerta o
vocabulário do domínio ("formata", "abnt", "busca"); o ramo semântico acerta paráfrase e
tema novo. Medido fora da amostra, juntos acertam mais que cada um sozinho em frases novas
sem perder nos comandos curtos do teste oficial (ver docs/pendencias.md).

Se o encoder não estiver disponível, o ramo semântico é ignorado, os pesos são
renormalizados e `ramos_ignorados_` diz quais ficaram de fora: o bot continua respondendo,
só com menos contexto.
"""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone

from encoder import EncoderIndisponivel


class Votacao(ClassifierMixin, BaseEstimator):
    def __init__(self, ramos):
        self.ramos = ramos          # lista de (nome, pipeline, peso)

    def fit(self, X, y):
        self.ramos_ajustados_ = [(nome, clone(pipe).fit(X, y), peso) for nome, pipe, peso in self.ramos]
        self.classes_ = self.ramos_ajustados_[0][1].classes_
        self.ramos_ignorados_: list[str] = []
        return self

    def predict_proba(self, X):
        soma, pesos, ignorados = 0.0, 0.0, []
        for nome, pipe, peso in self.ramos_ajustados_:
            try:
                probs = pipe.predict_proba(X)
            except EncoderIndisponivel:
                ignorados.append(nome)
                continue
            soma = soma + peso * probs
            pesos += peso
        if not pesos:
            raise EncoderIndisponivel("nenhum ramo do classificador pôde ser executado")
        self.ramos_ignorados_ = ignorados
        return soma / pesos

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]
