var path = require('path');
var fileBuildPath = path.resolve(process.cwd());

module.exports = {
    target: "node",
    mode: "production",
    devtool: 'source-map',
    entry: "./PackageAndUpload.js",
	resolve: {
		modules: ['node_modules']
	},
    output: {
        path: fileBuildPath,
	    filename: "PackageAndUpload_Release.js"
    },
	resolve: {
        extensions: [' ','.js', '.jsx','.json','.node']
    },
    module: {
        rules:[
            {
                test:/\.js$|\.jsx$/
            },
            {
                test: /\.json$/,use:'json-loader'
            },
            {
                test: /\.node$/,
				loader: "native-ext-loader",
				options: {
					rewritePath: "./lz4_depend"
				}
            }
        ]
    }

};