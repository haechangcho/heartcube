module.exports = {
  semanticLayerSync: ({ securityContext }) => [
    {
      type: "superset",
      name: "heartcube",
      url: "http://172.20.0.23:8088",
      auth: {
        username: "admin",
        password: "admin",
      },
    },
  ],
};
