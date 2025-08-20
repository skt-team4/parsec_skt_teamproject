// proxy-config.js
// Cloudflare Tunnel용 프록시 설정

const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // 챗봇 API 프록시
  app.use(
    '/api/chat',
    createProxyMiddleware({
      target: 'http://localhost:8000',
      changeOrigin: true,
      pathRewrite: {
        '^/api/chat': '/chat',
      },
    })
  );

  // 음식 인식 API 프록시
  app.use(
    '/api/food',
    createProxyMiddleware({
      target: 'http://localhost:5001',
      changeOrigin: true,
      pathRewrite: {
        '^/api/food': '',
      },
    })
  );

  // 영양 분석 API 프록시
  app.use(
    '/api/nutrition',
    createProxyMiddleware({
      target: 'http://localhost:5003',
      changeOrigin: true,
      pathRewrite: {
        '^/api/nutrition': '',
      },
    })
  );
};