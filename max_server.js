const Max = require('max-api');
const { Server } = require("socket.io");

const PORT = 5002;
const ROUTE = "test";   // default selector for the manual output_* test triggers
const MAX_BUFFER_BYTES = 32 * 1024 * 1024;   // 32 MB per message (~15s stereo @ 44.1k as JSON);
                                             // caps incoming Python->Max sends. The sync Python
                                             // client has no receive cap of its own.

// --- deliver a typed value into the Max patch ---------------------------------
// `route` is the outlet selector the value is routed to (e.g. "test" ->
// `route test`), chosen per-request by the Python caller. Types come from the
// Python client: int / float / symbol / list / dict.
function outletTyped(route, type, value) {
	switch (type) {
		case 'int':
		case 'float':
		case 'symbol':
			Max.outlet(route, value);
			break;
		case 'list':
			Max.outlet(route, ...value);   // spread atoms
			break;
		case 'dict':
			Max.outlet(route, value);      // JS object -> Max dictionary
			break;
		default:
			Max.post('unknown type: ' + type);
	}
}


// --- Socket.IO server: receive typed requests from Python ---------------------
// Default namespace + port 5002 to match the Python client (max_client.py).

const pending = [];   // FIFO of request_ids awaiting a patch reply
const io = new Server(PORT, {
	maxHttpBufferSize: MAX_BUFFER_BYTES,
	cors: { origin: "*" },
});

io.on('connection', (socket) => {
	Max.post('python client connected: ' + socket.id);

	socket.on('request', (data) => {
		const { route, type, value, request_id } = data;
		pending.push(request_id);
		outletTyped(route, type, value);
	});

	// Fire-and-forget from Python's `emit`: route the value but do NOT push a
	// request_id, so it stays out of the FIFO and never expects/steals a reply.
	socket.on('emit', (data) => {
		const { route, type, value } = data;
		outletTyped(route, type, value);
	});

	socket.on('disconnect', () => {
		Max.post('python client disconnected');
	});
});

// --- patch reply -> forward to Python (FIFO-correlated) -----------------------
// The patch sends `response <value>` back into node.script; we pair it with the
// oldest pending request_id and emit it to the client.
Max.addHandler('response', async (...args) => {
	const request_id = pending.shift();
	if (request_id === undefined) {
		Max.post('response with no pending request');
		return;
	}
	let results;
	if (args[0] === 'dictionary' && args.length === 2) {
		results = await Max.getDict(args[1]);       // resolve dict content by name
	} else {
		results = args.length === 1 ? args[0] : args;
	}
	io.emit('response', { request_id, results });
});
