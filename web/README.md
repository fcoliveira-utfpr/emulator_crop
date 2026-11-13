# Aplicação web do cropemu

Protótipo estático em Vite. Requer Node.js e npm.

```sh
npm install
npm run dev
```

O protótipo carrega os cartões e os modelos ONNX no navegador. A tela de previsão ainda não executa a estimativa: falta portar e validar o preparo diário de clima, o perfil de solo/hidráulica e a composição dos vetores de entrada conforme `../plano.md`.

Os modelos e cartões em `public/models/` foram copiados de `../packages/cropemu/src/cropemu/zoo/`; ao atualizar os modelos do pacote, atualizar também estes arquivos.

