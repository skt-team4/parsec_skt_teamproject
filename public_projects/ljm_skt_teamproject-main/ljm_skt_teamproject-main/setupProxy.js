const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
  // 백엔드 서비스 프록시 설정
  const services = {
    '/api/5001': 'http://localhost:5001',
    '/api/5002': 'http://localhost:5002', 
    '/api/5003': 'http://localhost:5003',
    '/api/5004': 'http://localhost:5004',
    '/api/5007': 'http://localhost:5007',
    '/api/8000': 'http://localhost:8000',
    '/api/8080': 'http://localhost:8080',
  };

  Object.entries(services).forEach(([path, target]) => {
    app.use(
      path,
      createProxyMiddleware({
        target: target,
        changeOrigin: true,
        pathRewrite: {
          [`^${path}`]: '',
        },
        onError: (err, req, res) => {
          console.error(`Proxy error for ${path}:`, err);
          res.status(503).json({ 
            error: 'Service unavailable',
            service: path,
            message: err.message 
          });
        },
      })
    );
  });
};