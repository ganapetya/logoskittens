/*eslint-disable block-scoped-var, id-length, no-control-regex, no-magic-numbers, no-mixed-operators, no-prototype-builtins, no-redeclare, no-shadow, no-var, sort-vars, default-case, jsdoc/require-param*/
import $protobuf from "protobufjs/minimal.js";

// Common aliases
const $Reader = $protobuf.Reader, $Writer = $protobuf.Writer, $util = $protobuf.util;
const $Object = $util.global.Object, $undefined = $util.global.undefined, $Error = $util.global.Error, $RangeError = $util.global.RangeError, $TypeError = $util.global.TypeError, $Number = $util.global.Number, $isFinite = $util.global.isFinite, $String = $util.global.String, $Array = $util.global.Array;

// Exported root namespace
const $root = $protobuf.roots["default"] || ($protobuf.roots["default"] = {});

export const cerm = $root.cerm = (() => {

    /**
     * Namespace cerm.
     * @exports cerm
     * @namespace
     */
    const cerm = {};

    cerm.execution = (function() {

        /**
         * Namespace execution.
         * @memberof cerm
         * @namespace
         */
        const execution = {};

        execution.v1 = (function() {

            /**
             * Namespace v1.
             * @memberof cerm.execution
             * @namespace
             */
            const v1 = {};

            /**
             * EmotionType enum.
             * @name cerm.execution.v1.EmotionType
             * @enum {number}
             * @property {number} EMOTION_NEUTRAL=0 EMOTION_NEUTRAL value
             * @property {number} EMOTION_CURIOSITY=1 EMOTION_CURIOSITY value
             * @property {number} EMOTION_DISAPPOINTMENT=2 EMOTION_DISAPPOINTMENT value
             * @property {number} EMOTION_AMUSEMENT=3 EMOTION_AMUSEMENT value
             * @property {number} EMOTION_ENCOURAGEMENT=4 EMOTION_ENCOURAGEMENT value
             * @property {number} EMOTION_FRUSTRATION=5 EMOTION_FRUSTRATION value
             */
            v1.EmotionType = (function() {
                const valuesById = $Object.create(null), values = $Object.create(valuesById);
                values[valuesById[0] = "EMOTION_NEUTRAL"] = 0;
                values[valuesById[1] = "EMOTION_CURIOSITY"] = 1;
                values[valuesById[2] = "EMOTION_DISAPPOINTMENT"] = 2;
                values[valuesById[3] = "EMOTION_AMUSEMENT"] = 3;
                values[valuesById[4] = "EMOTION_ENCOURAGEMENT"] = 4;
                values[valuesById[5] = "EMOTION_FRUSTRATION"] = 5;
                return values;
            })();

            v1.Vector3 = (function() {

                /**
                 * Properties of a Vector3.
                 * @typedef {Object} cerm.execution.v1.Vector3.$Properties
                 * @property {number|null} [x] Vector3 x
                 * @property {number|null} [y] Vector3 y
                 * @property {number|null} [z] Vector3 z
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */

                /**
                 * Properties of a Vector3.
                 * @memberof cerm.execution.v1
                 * @interface IVector3
                 * @augments cerm.execution.v1.Vector3.$Properties
                 * @deprecated Use cerm.execution.v1.Vector3.$Properties instead.
                 */

                /**
                 * Shape of a Vector3.
                 * @typedef {cerm.execution.v1.Vector3.$Properties} cerm.execution.v1.Vector3.$Shape
                 */

                /**
                 * Constructs a new Vector3.
                 * @memberof cerm.execution.v1
                 * @classdesc Represents a Vector3.
                 * @constructor
                 * @param {cerm.execution.v1.Vector3.$Properties=} [properties] Properties to set
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */
                const Vector3 = function (properties) {
                    if (properties)
                        for (let keys = $Object.keys(properties), i = 0; i < keys.length; ++i)
                            if (properties[keys[i]] != null && keys[i] !== "__proto__")
                                this[keys[i]] = properties[keys[i]];
                };

                /**
                 * Vector3 x.
                 * @member {number} x
                 * @memberof cerm.execution.v1.Vector3
                 * @instance
                 */
                Vector3.prototype.x = 0;

                /**
                 * Vector3 y.
                 * @member {number} y
                 * @memberof cerm.execution.v1.Vector3
                 * @instance
                 */
                Vector3.prototype.y = 0;

                /**
                 * Vector3 z.
                 * @member {number} z
                 * @memberof cerm.execution.v1.Vector3
                 * @instance
                 */
                Vector3.prototype.z = 0;

                /**
                 * Creates a new Vector3 instance using the specified properties.
                 * @function create
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {cerm.execution.v1.Vector3.$Properties=} [properties] Properties to set
                 * @returns {cerm.execution.v1.Vector3} Vector3 instance
                 * @type {{
                 *   (properties: cerm.execution.v1.Vector3.$Shape): cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape;
                 *   (properties?: cerm.execution.v1.Vector3.$Properties): cerm.execution.v1.Vector3;
                 * }}
                 */
                Vector3.create = function(properties) {
                    return new Vector3(properties);
                };

                /**
                 * Encodes the specified Vector3 message. Does not implicitly {@link cerm.execution.v1.Vector3.verify|verify} messages.
                 * @function encode
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {cerm.execution.v1.Vector3.$Properties} message Vector3 message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                Vector3.encode = function (message, writer, _depth) {
                    if (!writer)
                        writer = $Writer.create();
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    if (message.x != null && $Object.hasOwnProperty.call(message, "x") && !$Object.is(message.x, 0))
                        writer.uint32(/* id 1, wireType 1 =*/9).double(message.x);
                    if (message.y != null && $Object.hasOwnProperty.call(message, "y") && !$Object.is(message.y, 0))
                        writer.uint32(/* id 2, wireType 1 =*/17).double(message.y);
                    if (message.z != null && $Object.hasOwnProperty.call(message, "z") && !$Object.is(message.z, 0))
                        writer.uint32(/* id 3, wireType 1 =*/25).double(message.z);
                    if (message.$unknowns != null && $Object.hasOwnProperty.call(message, "$unknowns"))
                        for (let i = 0; i < message.$unknowns.length; ++i)
                            writer.raw(message.$unknowns[i]);
                    return writer;
                };

                /**
                 * Encodes the specified Vector3 message, length delimited. Does not implicitly {@link cerm.execution.v1.Vector3.verify|verify} messages.
                 * @function encodeDelimited
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {cerm.execution.v1.Vector3.$Properties} message Vector3 message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                Vector3.encodeDelimited = function(message, writer) {
                    return this.encode(message, (writer || $Writer.create()).fork()).ldelim();
                };

                /**
                 * Decodes a Vector3 message from the specified reader or buffer.
                 * @function decode
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @param {number} [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape} Vector3
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                Vector3.decode = function (reader, length, _end, _depth, _target) {
                    if (!(reader instanceof $Reader))
                        reader = $Reader.create(reader);
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $Reader.recursionLimit)
                        throw $Error("max depth exceeded");
                    let end, message, value;
                    if (length === $undefined)
                        end = reader.len;
                    else {
                        end = reader.pos + length;
                        if (end > reader.len)
                            throw $RangeError("index out of range");
                        length = reader.len;
                        reader.len = end;
                    }
                    message = _target || new $root.cerm.execution.v1.Vector3();
                    while (reader.pos < end) {
                        let start = reader.pos;
                        let tag = reader.tag();
                        if (tag === _end) {
                            _end = $undefined;
                            break;
                        }
                        let wireType = tag & 7;
                        switch (tag >>>= 3) {
                        case 1: {
                                if (wireType !== 1)
                                    break;
                                if (!$Object.is(value = reader.double(), 0))
                                    message.x = value;
                                else
                                    delete message.x;
                                continue;
                            }
                        case 2: {
                                if (wireType !== 1)
                                    break;
                                if (!$Object.is(value = reader.double(), 0))
                                    message.y = value;
                                else
                                    delete message.y;
                                continue;
                            }
                        case 3: {
                                if (wireType !== 1)
                                    break;
                                if (!$Object.is(value = reader.double(), 0))
                                    message.z = value;
                                else
                                    delete message.z;
                                continue;
                            }
                        }
                        reader.skipType(wireType, _depth, tag);
                        if (!reader.discardUnknown) {
                            $util.makeProp(message, "$unknowns", false);
                            (message.$unknowns || (message.$unknowns = [])).push(reader.raw(start, reader.pos));
                        }
                    }
                    if (length !== $undefined) {
                        if (reader.pos !== end)
                            throw $RangeError("index out of range");
                        reader.len = length;
                    }
                    if (_end !== $undefined)
                        throw $Error("missing end group");
                    return message;
                };

                /**
                 * Decodes a Vector3 message from the specified reader or buffer, length delimited.
                 * @function decodeDelimited
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape} Vector3
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                Vector3.decodeDelimited = function(reader) {
                    if (!(reader instanceof $Reader))
                        reader = new $Reader(reader);
                    return this.decode(reader, reader.size());
                };

                /**
                 * Verifies a Vector3 message.
                 * @function verify
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {Object.<string,*>} message Plain object to verify
                 * @returns {string|null} `null` if valid, otherwise the reason why it is not
                 */
                Vector3.verify = function (message, _depth) {
                    if (typeof message !== "object" || message === null)
                        return "object expected";
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        return "max depth exceeded";
                    if (message.x != null && $Object.hasOwnProperty.call(message, "x"))
                        if (typeof message.x !== "number")
                            return "x: number expected";
                    if (message.y != null && $Object.hasOwnProperty.call(message, "y"))
                        if (typeof message.y !== "number")
                            return "y: number expected";
                    if (message.z != null && $Object.hasOwnProperty.call(message, "z"))
                        if (typeof message.z !== "number")
                            return "z: number expected";
                    return null;
                };

                /**
                 * Creates a Vector3 message from a plain object. Also converts values to their respective internal types.
                 * @function fromObject
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {Object.<string,*>} object Plain object
                 * @returns {cerm.execution.v1.Vector3} Vector3
                 */
                Vector3.fromObject = function (object, _depth) {
                    if (object instanceof $root.cerm.execution.v1.Vector3)
                        return object;
                    if (!$util.isObject(object))
                        throw $TypeError(".cerm.execution.v1.Vector3: object expected");
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let message = new $root.cerm.execution.v1.Vector3();
                    if (object.x != null)
                        if (!$Object.is($Number(object.x), 0))
                            message.x = $Number(object.x);
                    if (object.y != null)
                        if (!$Object.is($Number(object.y), 0))
                            message.y = $Number(object.y);
                    if (object.z != null)
                        if (!$Object.is($Number(object.z), 0))
                            message.z = $Number(object.z);
                    return message;
                };

                /**
                 * Creates a plain object from a Vector3 message. Also converts values to other types if specified.
                 * @function toObject
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {cerm.execution.v1.Vector3} message Vector3
                 * @param {$protobuf.IConversionOptions} [options] Conversion options
                 * @returns {Object.<string,*>} Plain object
                 */
                Vector3.toObject = function (message, options, _depth) {
                    if (!options)
                        options = {};
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let object = {};
                    if (options.defaults) {
                        object.x = 0;
                        object.y = 0;
                        object.z = 0;
                    }
                    if (message.x != null && $Object.hasOwnProperty.call(message, "x"))
                        object.x = options.json && !$isFinite(message.x) ? $String(message.x) : message.x;
                    if (message.y != null && $Object.hasOwnProperty.call(message, "y"))
                        object.y = options.json && !$isFinite(message.y) ? $String(message.y) : message.y;
                    if (message.z != null && $Object.hasOwnProperty.call(message, "z"))
                        object.z = options.json && !$isFinite(message.z) ? $String(message.z) : message.z;
                    return object;
                };

                /**
                 * Converts this Vector3 to JSON.
                 * @function toJSON
                 * @memberof cerm.execution.v1.Vector3
                 * @instance
                 * @returns {Object.<string,*>} JSON object
                 */
                Vector3.prototype.toJSON = function() {
                    return Vector3.toObject(this, $protobuf.util.toJSONOptions);
                };

                /**
                 * Gets the type url for Vector3
                 * @function getTypeUrl
                 * @memberof cerm.execution.v1.Vector3
                 * @static
                 * @param {string} [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns {string} The type url
                 */
                Vector3.getTypeUrl = function(prefix) {
                    if (prefix === $undefined)
                        prefix = "type.googleapis.com";
                    return prefix + "/cerm.execution.v1.Vector3";
                };

                return Vector3;
            })();

            v1.AudioPayload = (function() {

                /**
                 * Properties of an AudioPayload.
                 * @typedef {Object} cerm.execution.v1.AudioPayload.$Properties
                 * @property {string|null} [text] AudioPayload text
                 * @property {string|null} [languageCode] AudioPayload languageCode
                 * @property {string|null} [voiceModelId] AudioPayload voiceModelId
                 * @property {Uint8Array|null} [precomputedAudioPcm] AudioPayload precomputedAudioPcm
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */

                /**
                 * Properties of an AudioPayload.
                 * @memberof cerm.execution.v1
                 * @interface IAudioPayload
                 * @augments cerm.execution.v1.AudioPayload.$Properties
                 * @deprecated Use cerm.execution.v1.AudioPayload.$Properties instead.
                 */

                /**
                 * Shape of an AudioPayload.
                 * @typedef {cerm.execution.v1.AudioPayload.$Properties} cerm.execution.v1.AudioPayload.$Shape
                 */

                /**
                 * Constructs a new AudioPayload.
                 * @memberof cerm.execution.v1
                 * @classdesc Represents an AudioPayload.
                 * @constructor
                 * @param {cerm.execution.v1.AudioPayload.$Properties=} [properties] Properties to set
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */
                const AudioPayload = function (properties) {
                    if (properties)
                        for (let keys = $Object.keys(properties), i = 0; i < keys.length; ++i)
                            if (properties[keys[i]] != null && keys[i] !== "__proto__")
                                this[keys[i]] = properties[keys[i]];
                };

                /**
                 * AudioPayload text.
                 * @member {string} text
                 * @memberof cerm.execution.v1.AudioPayload
                 * @instance
                 */
                AudioPayload.prototype.text = "";

                /**
                 * AudioPayload languageCode.
                 * @member {string} languageCode
                 * @memberof cerm.execution.v1.AudioPayload
                 * @instance
                 */
                AudioPayload.prototype.languageCode = "";

                /**
                 * AudioPayload voiceModelId.
                 * @member {string} voiceModelId
                 * @memberof cerm.execution.v1.AudioPayload
                 * @instance
                 */
                AudioPayload.prototype.voiceModelId = "";

                /**
                 * AudioPayload precomputedAudioPcm.
                 * @member {Uint8Array} precomputedAudioPcm
                 * @memberof cerm.execution.v1.AudioPayload
                 * @instance
                 */
                AudioPayload.prototype.precomputedAudioPcm = $util.newBuffer([]);

                /**
                 * Creates a new AudioPayload instance using the specified properties.
                 * @function create
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {cerm.execution.v1.AudioPayload.$Properties=} [properties] Properties to set
                 * @returns {cerm.execution.v1.AudioPayload} AudioPayload instance
                 * @type {{
                 *   (properties: cerm.execution.v1.AudioPayload.$Shape): cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape;
                 *   (properties?: cerm.execution.v1.AudioPayload.$Properties): cerm.execution.v1.AudioPayload;
                 * }}
                 */
                AudioPayload.create = function(properties) {
                    return new AudioPayload(properties);
                };

                /**
                 * Encodes the specified AudioPayload message. Does not implicitly {@link cerm.execution.v1.AudioPayload.verify|verify} messages.
                 * @function encode
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {cerm.execution.v1.AudioPayload.$Properties} message AudioPayload message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                AudioPayload.encode = function (message, writer, _depth) {
                    if (!writer)
                        writer = $Writer.create();
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    if (message.text != null && $Object.hasOwnProperty.call(message, "text") && message.text !== "")
                        writer.uint32(/* id 1, wireType 2 =*/10).string(message.text);
                    if (message.languageCode != null && $Object.hasOwnProperty.call(message, "languageCode") && message.languageCode !== "")
                        writer.uint32(/* id 2, wireType 2 =*/18).string(message.languageCode);
                    if (message.voiceModelId != null && $Object.hasOwnProperty.call(message, "voiceModelId") && message.voiceModelId !== "")
                        writer.uint32(/* id 3, wireType 2 =*/26).string(message.voiceModelId);
                    if (message.precomputedAudioPcm != null && $Object.hasOwnProperty.call(message, "precomputedAudioPcm") && message.precomputedAudioPcm.length)
                        writer.uint32(/* id 4, wireType 2 =*/34).bytes(message.precomputedAudioPcm);
                    if (message.$unknowns != null && $Object.hasOwnProperty.call(message, "$unknowns"))
                        for (let i = 0; i < message.$unknowns.length; ++i)
                            writer.raw(message.$unknowns[i]);
                    return writer;
                };

                /**
                 * Encodes the specified AudioPayload message, length delimited. Does not implicitly {@link cerm.execution.v1.AudioPayload.verify|verify} messages.
                 * @function encodeDelimited
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {cerm.execution.v1.AudioPayload.$Properties} message AudioPayload message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                AudioPayload.encodeDelimited = function(message, writer) {
                    return this.encode(message, (writer || $Writer.create()).fork()).ldelim();
                };

                /**
                 * Decodes an AudioPayload message from the specified reader or buffer.
                 * @function decode
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @param {number} [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape} AudioPayload
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                AudioPayload.decode = function (reader, length, _end, _depth, _target) {
                    if (!(reader instanceof $Reader))
                        reader = $Reader.create(reader);
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $Reader.recursionLimit)
                        throw $Error("max depth exceeded");
                    let end, message, value;
                    if (length === $undefined)
                        end = reader.len;
                    else {
                        end = reader.pos + length;
                        if (end > reader.len)
                            throw $RangeError("index out of range");
                        length = reader.len;
                        reader.len = end;
                    }
                    message = _target || new $root.cerm.execution.v1.AudioPayload();
                    while (reader.pos < end) {
                        let start = reader.pos;
                        let tag = reader.tag();
                        if (tag === _end) {
                            _end = $undefined;
                            break;
                        }
                        let wireType = tag & 7;
                        switch (tag >>>= 3) {
                        case 1: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.text = value;
                                else
                                    delete message.text;
                                continue;
                            }
                        case 2: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.languageCode = value;
                                else
                                    delete message.languageCode;
                                continue;
                            }
                        case 3: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.voiceModelId = value;
                                else
                                    delete message.voiceModelId;
                                continue;
                            }
                        case 4: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.bytes()).length)
                                    message.precomputedAudioPcm = value;
                                else
                                    delete message.precomputedAudioPcm;
                                continue;
                            }
                        }
                        reader.skipType(wireType, _depth, tag);
                        if (!reader.discardUnknown) {
                            $util.makeProp(message, "$unknowns", false);
                            (message.$unknowns || (message.$unknowns = [])).push(reader.raw(start, reader.pos));
                        }
                    }
                    if (length !== $undefined) {
                        if (reader.pos !== end)
                            throw $RangeError("index out of range");
                        reader.len = length;
                    }
                    if (_end !== $undefined)
                        throw $Error("missing end group");
                    return message;
                };

                /**
                 * Decodes an AudioPayload message from the specified reader or buffer, length delimited.
                 * @function decodeDelimited
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape} AudioPayload
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                AudioPayload.decodeDelimited = function(reader) {
                    if (!(reader instanceof $Reader))
                        reader = new $Reader(reader);
                    return this.decode(reader, reader.size());
                };

                /**
                 * Verifies an AudioPayload message.
                 * @function verify
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {Object.<string,*>} message Plain object to verify
                 * @returns {string|null} `null` if valid, otherwise the reason why it is not
                 */
                AudioPayload.verify = function (message, _depth) {
                    if (typeof message !== "object" || message === null)
                        return "object expected";
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        return "max depth exceeded";
                    if (message.text != null && $Object.hasOwnProperty.call(message, "text"))
                        if (!$util.isString(message.text))
                            return "text: string expected";
                    if (message.languageCode != null && $Object.hasOwnProperty.call(message, "languageCode"))
                        if (!$util.isString(message.languageCode))
                            return "languageCode: string expected";
                    if (message.voiceModelId != null && $Object.hasOwnProperty.call(message, "voiceModelId"))
                        if (!$util.isString(message.voiceModelId))
                            return "voiceModelId: string expected";
                    if (message.precomputedAudioPcm != null && $Object.hasOwnProperty.call(message, "precomputedAudioPcm"))
                        if (!(message.precomputedAudioPcm && typeof message.precomputedAudioPcm.length === "number" || $util.isString(message.precomputedAudioPcm)))
                            return "precomputedAudioPcm: buffer expected";
                    return null;
                };

                /**
                 * Creates an AudioPayload message from a plain object. Also converts values to their respective internal types.
                 * @function fromObject
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {Object.<string,*>} object Plain object
                 * @returns {cerm.execution.v1.AudioPayload} AudioPayload
                 */
                AudioPayload.fromObject = function (object, _depth) {
                    if (object instanceof $root.cerm.execution.v1.AudioPayload)
                        return object;
                    if (!$util.isObject(object))
                        throw $TypeError(".cerm.execution.v1.AudioPayload: object expected");
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let message = new $root.cerm.execution.v1.AudioPayload();
                    if (object.text != null)
                        if (typeof object.text !== "string" || object.text.length)
                            message.text = $String(object.text);
                    if (object.languageCode != null)
                        if (typeof object.languageCode !== "string" || object.languageCode.length)
                            message.languageCode = $String(object.languageCode);
                    if (object.voiceModelId != null)
                        if (typeof object.voiceModelId !== "string" || object.voiceModelId.length)
                            message.voiceModelId = $String(object.voiceModelId);
                    if (object.precomputedAudioPcm != null)
                        if (object.precomputedAudioPcm.length)
                            if (typeof object.precomputedAudioPcm === "string")
                                $util.base64.decode(object.precomputedAudioPcm, message.precomputedAudioPcm = $util.newBuffer($util.base64.length(object.precomputedAudioPcm)), 0);
                            else if (object.precomputedAudioPcm.length >= 0)
                                message.precomputedAudioPcm = object.precomputedAudioPcm;
                    return message;
                };

                /**
                 * Creates a plain object from an AudioPayload message. Also converts values to other types if specified.
                 * @function toObject
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {cerm.execution.v1.AudioPayload} message AudioPayload
                 * @param {$protobuf.IConversionOptions} [options] Conversion options
                 * @returns {Object.<string,*>} Plain object
                 */
                AudioPayload.toObject = function (message, options, _depth) {
                    if (!options)
                        options = {};
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let object = {};
                    if (options.defaults) {
                        object.text = "";
                        object.languageCode = "";
                        object.voiceModelId = "";
                        if (options.bytes === $String)
                            object.precomputedAudioPcm = "";
                        else {
                            object.precomputedAudioPcm = [];
                            if (options.bytes !== $Array)
                                object.precomputedAudioPcm = $util.newBuffer(object.precomputedAudioPcm);
                        }
                    }
                    if (message.text != null && $Object.hasOwnProperty.call(message, "text"))
                        object.text = message.text;
                    if (message.languageCode != null && $Object.hasOwnProperty.call(message, "languageCode"))
                        object.languageCode = message.languageCode;
                    if (message.voiceModelId != null && $Object.hasOwnProperty.call(message, "voiceModelId"))
                        object.voiceModelId = message.voiceModelId;
                    if (message.precomputedAudioPcm != null && $Object.hasOwnProperty.call(message, "precomputedAudioPcm"))
                        object.precomputedAudioPcm = options.bytes === $String ? $util.base64.encode(message.precomputedAudioPcm, 0, message.precomputedAudioPcm.length) : options.bytes === $Array ? $Array.prototype.slice.call(message.precomputedAudioPcm) : message.precomputedAudioPcm;
                    return object;
                };

                /**
                 * Converts this AudioPayload to JSON.
                 * @function toJSON
                 * @memberof cerm.execution.v1.AudioPayload
                 * @instance
                 * @returns {Object.<string,*>} JSON object
                 */
                AudioPayload.prototype.toJSON = function() {
                    return AudioPayload.toObject(this, $protobuf.util.toJSONOptions);
                };

                /**
                 * Gets the type url for AudioPayload
                 * @function getTypeUrl
                 * @memberof cerm.execution.v1.AudioPayload
                 * @static
                 * @param {string} [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns {string} The type url
                 */
                AudioPayload.getTypeUrl = function(prefix) {
                    if (prefix === $undefined)
                        prefix = "type.googleapis.com";
                    return prefix + "/cerm.execution.v1.AudioPayload";
                };

                return AudioPayload;
            })();

            v1.KinematicGesture = (function() {

                /**
                 * Properties of a KinematicGesture.
                 * @typedef {Object} cerm.execution.v1.KinematicGesture.$Properties
                 * @property {string|null} [primitiveName] KinematicGesture primitiveName
                 * @property {cerm.execution.v1.Vector3.$Properties|null} [targetVector] KinematicGesture targetVector
                 * @property {number|null} [durationMs] KinematicGesture durationMs
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */

                /**
                 * Properties of a KinematicGesture.
                 * @memberof cerm.execution.v1
                 * @interface IKinematicGesture
                 * @augments cerm.execution.v1.KinematicGesture.$Properties
                 * @deprecated Use cerm.execution.v1.KinematicGesture.$Properties instead.
                 */

                /**
                 * Shape of a KinematicGesture.
                 * @typedef {cerm.execution.v1.KinematicGesture.$Properties} cerm.execution.v1.KinematicGesture.$Shape
                 */

                /**
                 * Constructs a new KinematicGesture.
                 * @memberof cerm.execution.v1
                 * @classdesc Represents a KinematicGesture.
                 * @constructor
                 * @param {cerm.execution.v1.KinematicGesture.$Properties=} [properties] Properties to set
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */
                const KinematicGesture = function (properties) {
                    if (properties)
                        for (let keys = $Object.keys(properties), i = 0; i < keys.length; ++i)
                            if (properties[keys[i]] != null && keys[i] !== "__proto__")
                                this[keys[i]] = properties[keys[i]];
                };

                /**
                 * KinematicGesture primitiveName.
                 * @member {string} primitiveName
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @instance
                 */
                KinematicGesture.prototype.primitiveName = "";

                /**
                 * KinematicGesture targetVector.
                 * @member {cerm.execution.v1.Vector3.$Properties|null|undefined} targetVector
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @instance
                 */
                KinematicGesture.prototype.targetVector = null;

                /**
                 * KinematicGesture durationMs.
                 * @member {number} durationMs
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @instance
                 */
                KinematicGesture.prototype.durationMs = 0;

                /**
                 * Creates a new KinematicGesture instance using the specified properties.
                 * @function create
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {cerm.execution.v1.KinematicGesture.$Properties=} [properties] Properties to set
                 * @returns {cerm.execution.v1.KinematicGesture} KinematicGesture instance
                 * @type {{
                 *   (properties: cerm.execution.v1.KinematicGesture.$Shape): cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape;
                 *   (properties?: cerm.execution.v1.KinematicGesture.$Properties): cerm.execution.v1.KinematicGesture;
                 * }}
                 */
                KinematicGesture.create = function(properties) {
                    return new KinematicGesture(properties);
                };

                /**
                 * Encodes the specified KinematicGesture message. Does not implicitly {@link cerm.execution.v1.KinematicGesture.verify|verify} messages.
                 * @function encode
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {cerm.execution.v1.KinematicGesture.$Properties} message KinematicGesture message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                KinematicGesture.encode = function (message, writer, _depth) {
                    if (!writer)
                        writer = $Writer.create();
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    if (message.primitiveName != null && $Object.hasOwnProperty.call(message, "primitiveName") && message.primitiveName !== "")
                        writer.uint32(/* id 1, wireType 2 =*/10).string(message.primitiveName);
                    if (message.targetVector != null && $Object.hasOwnProperty.call(message, "targetVector"))
                        $root.cerm.execution.v1.Vector3.encode(message.targetVector, writer.uint32(/* id 2, wireType 2 =*/18).fork(), _depth + 1).ldelim();
                    if (message.durationMs != null && $Object.hasOwnProperty.call(message, "durationMs") && !$Object.is(message.durationMs, 0))
                        writer.uint32(/* id 3, wireType 1 =*/25).double(message.durationMs);
                    if (message.$unknowns != null && $Object.hasOwnProperty.call(message, "$unknowns"))
                        for (let i = 0; i < message.$unknowns.length; ++i)
                            writer.raw(message.$unknowns[i]);
                    return writer;
                };

                /**
                 * Encodes the specified KinematicGesture message, length delimited. Does not implicitly {@link cerm.execution.v1.KinematicGesture.verify|verify} messages.
                 * @function encodeDelimited
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {cerm.execution.v1.KinematicGesture.$Properties} message KinematicGesture message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                KinematicGesture.encodeDelimited = function(message, writer) {
                    return this.encode(message, (writer || $Writer.create()).fork()).ldelim();
                };

                /**
                 * Decodes a KinematicGesture message from the specified reader or buffer.
                 * @function decode
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @param {number} [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape} KinematicGesture
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                KinematicGesture.decode = function (reader, length, _end, _depth, _target) {
                    if (!(reader instanceof $Reader))
                        reader = $Reader.create(reader);
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $Reader.recursionLimit)
                        throw $Error("max depth exceeded");
                    let end, message, value;
                    if (length === $undefined)
                        end = reader.len;
                    else {
                        end = reader.pos + length;
                        if (end > reader.len)
                            throw $RangeError("index out of range");
                        length = reader.len;
                        reader.len = end;
                    }
                    message = _target || new $root.cerm.execution.v1.KinematicGesture();
                    while (reader.pos < end) {
                        let start = reader.pos;
                        let tag = reader.tag();
                        if (tag === _end) {
                            _end = $undefined;
                            break;
                        }
                        let wireType = tag & 7;
                        switch (tag >>>= 3) {
                        case 1: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.primitiveName = value;
                                else
                                    delete message.primitiveName;
                                continue;
                            }
                        case 2: {
                                if (wireType !== 2)
                                    break;
                                message.targetVector = $root.cerm.execution.v1.Vector3.decode(reader, reader.size(), $undefined, _depth + 1, message.targetVector);
                                continue;
                            }
                        case 3: {
                                if (wireType !== 1)
                                    break;
                                if (!$Object.is(value = reader.double(), 0))
                                    message.durationMs = value;
                                else
                                    delete message.durationMs;
                                continue;
                            }
                        }
                        reader.skipType(wireType, _depth, tag);
                        if (!reader.discardUnknown) {
                            $util.makeProp(message, "$unknowns", false);
                            (message.$unknowns || (message.$unknowns = [])).push(reader.raw(start, reader.pos));
                        }
                    }
                    if (length !== $undefined) {
                        if (reader.pos !== end)
                            throw $RangeError("index out of range");
                        reader.len = length;
                    }
                    if (_end !== $undefined)
                        throw $Error("missing end group");
                    return message;
                };

                /**
                 * Decodes a KinematicGesture message from the specified reader or buffer, length delimited.
                 * @function decodeDelimited
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape} KinematicGesture
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                KinematicGesture.decodeDelimited = function(reader) {
                    if (!(reader instanceof $Reader))
                        reader = new $Reader(reader);
                    return this.decode(reader, reader.size());
                };

                /**
                 * Verifies a KinematicGesture message.
                 * @function verify
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {Object.<string,*>} message Plain object to verify
                 * @returns {string|null} `null` if valid, otherwise the reason why it is not
                 */
                KinematicGesture.verify = function (message, _depth) {
                    if (typeof message !== "object" || message === null)
                        return "object expected";
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        return "max depth exceeded";
                    if (message.primitiveName != null && $Object.hasOwnProperty.call(message, "primitiveName"))
                        if (!$util.isString(message.primitiveName))
                            return "primitiveName: string expected";
                    if (message.targetVector != null && $Object.hasOwnProperty.call(message, "targetVector")) {
                        let error = $root.cerm.execution.v1.Vector3.verify(message.targetVector, _depth + 1);
                        if (error)
                            return "targetVector." + error;
                    }
                    if (message.durationMs != null && $Object.hasOwnProperty.call(message, "durationMs"))
                        if (typeof message.durationMs !== "number")
                            return "durationMs: number expected";
                    return null;
                };

                /**
                 * Creates a KinematicGesture message from a plain object. Also converts values to their respective internal types.
                 * @function fromObject
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {Object.<string,*>} object Plain object
                 * @returns {cerm.execution.v1.KinematicGesture} KinematicGesture
                 */
                KinematicGesture.fromObject = function (object, _depth) {
                    if (object instanceof $root.cerm.execution.v1.KinematicGesture)
                        return object;
                    if (!$util.isObject(object))
                        throw $TypeError(".cerm.execution.v1.KinematicGesture: object expected");
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let message = new $root.cerm.execution.v1.KinematicGesture();
                    if (object.primitiveName != null)
                        if (typeof object.primitiveName !== "string" || object.primitiveName.length)
                            message.primitiveName = $String(object.primitiveName);
                    if (object.targetVector != null) {
                        if (!$util.isObject(object.targetVector))
                            throw $TypeError(".cerm.execution.v1.KinematicGesture.targetVector: object expected");
                        message.targetVector = $root.cerm.execution.v1.Vector3.fromObject(object.targetVector, _depth + 1);
                    }
                    if (object.durationMs != null)
                        if (!$Object.is($Number(object.durationMs), 0))
                            message.durationMs = $Number(object.durationMs);
                    return message;
                };

                /**
                 * Creates a plain object from a KinematicGesture message. Also converts values to other types if specified.
                 * @function toObject
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {cerm.execution.v1.KinematicGesture} message KinematicGesture
                 * @param {$protobuf.IConversionOptions} [options] Conversion options
                 * @returns {Object.<string,*>} Plain object
                 */
                KinematicGesture.toObject = function (message, options, _depth) {
                    if (!options)
                        options = {};
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let object = {};
                    if (options.defaults) {
                        object.primitiveName = "";
                        object.targetVector = null;
                        object.durationMs = 0;
                    }
                    if (message.primitiveName != null && $Object.hasOwnProperty.call(message, "primitiveName"))
                        object.primitiveName = message.primitiveName;
                    if (message.targetVector != null && $Object.hasOwnProperty.call(message, "targetVector"))
                        object.targetVector = $root.cerm.execution.v1.Vector3.toObject(message.targetVector, options, _depth + 1);
                    if (message.durationMs != null && $Object.hasOwnProperty.call(message, "durationMs"))
                        object.durationMs = options.json && !$isFinite(message.durationMs) ? $String(message.durationMs) : message.durationMs;
                    return object;
                };

                /**
                 * Converts this KinematicGesture to JSON.
                 * @function toJSON
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @instance
                 * @returns {Object.<string,*>} JSON object
                 */
                KinematicGesture.prototype.toJSON = function() {
                    return KinematicGesture.toObject(this, $protobuf.util.toJSONOptions);
                };

                /**
                 * Gets the type url for KinematicGesture
                 * @function getTypeUrl
                 * @memberof cerm.execution.v1.KinematicGesture
                 * @static
                 * @param {string} [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns {string} The type url
                 */
                KinematicGesture.getTypeUrl = function(prefix) {
                    if (prefix === $undefined)
                        prefix = "type.googleapis.com";
                    return prefix + "/cerm.execution.v1.KinematicGesture";
                };

                return KinematicGesture;
            })();

            v1.ScreenVisualCue = (function() {

                /**
                 * Properties of a ScreenVisualCue.
                 * @typedef {Object} cerm.execution.v1.ScreenVisualCue.$Properties
                 * @property {string|null} [animationId] ScreenVisualCue animationId
                 * @property {string|null} [focusTargetId] ScreenVisualCue focusTargetId
                 * @property {Array.<string>|null} [highlightElements] ScreenVisualCue highlightElements
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */

                /**
                 * Properties of a ScreenVisualCue.
                 * @memberof cerm.execution.v1
                 * @interface IScreenVisualCue
                 * @augments cerm.execution.v1.ScreenVisualCue.$Properties
                 * @deprecated Use cerm.execution.v1.ScreenVisualCue.$Properties instead.
                 */

                /**
                 * Shape of a ScreenVisualCue.
                 * @typedef {cerm.execution.v1.ScreenVisualCue.$Properties} cerm.execution.v1.ScreenVisualCue.$Shape
                 */

                /**
                 * Constructs a new ScreenVisualCue.
                 * @memberof cerm.execution.v1
                 * @classdesc Represents a ScreenVisualCue.
                 * @constructor
                 * @param {cerm.execution.v1.ScreenVisualCue.$Properties=} [properties] Properties to set
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */
                const ScreenVisualCue = function (properties) {
                    this.highlightElements = [];
                    if (properties)
                        for (let keys = $Object.keys(properties), i = 0; i < keys.length; ++i)
                            if (properties[keys[i]] != null && keys[i] !== "__proto__")
                                this[keys[i]] = properties[keys[i]];
                };

                /**
                 * ScreenVisualCue animationId.
                 * @member {string} animationId
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @instance
                 */
                ScreenVisualCue.prototype.animationId = "";

                /**
                 * ScreenVisualCue focusTargetId.
                 * @member {string} focusTargetId
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @instance
                 */
                ScreenVisualCue.prototype.focusTargetId = "";

                /**
                 * ScreenVisualCue highlightElements.
                 * @member {Array.<string>} highlightElements
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @instance
                 */
                ScreenVisualCue.prototype.highlightElements = $util.emptyArray;

                /**
                 * Creates a new ScreenVisualCue instance using the specified properties.
                 * @function create
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {cerm.execution.v1.ScreenVisualCue.$Properties=} [properties] Properties to set
                 * @returns {cerm.execution.v1.ScreenVisualCue} ScreenVisualCue instance
                 * @type {{
                 *   (properties: cerm.execution.v1.ScreenVisualCue.$Shape): cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape;
                 *   (properties?: cerm.execution.v1.ScreenVisualCue.$Properties): cerm.execution.v1.ScreenVisualCue;
                 * }}
                 */
                ScreenVisualCue.create = function(properties) {
                    return new ScreenVisualCue(properties);
                };

                /**
                 * Encodes the specified ScreenVisualCue message. Does not implicitly {@link cerm.execution.v1.ScreenVisualCue.verify|verify} messages.
                 * @function encode
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {cerm.execution.v1.ScreenVisualCue.$Properties} message ScreenVisualCue message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                ScreenVisualCue.encode = function (message, writer, _depth) {
                    if (!writer)
                        writer = $Writer.create();
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    if (message.animationId != null && $Object.hasOwnProperty.call(message, "animationId") && message.animationId !== "")
                        writer.uint32(/* id 1, wireType 2 =*/10).string(message.animationId);
                    if (message.focusTargetId != null && $Object.hasOwnProperty.call(message, "focusTargetId") && message.focusTargetId !== "")
                        writer.uint32(/* id 2, wireType 2 =*/18).string(message.focusTargetId);
                    if (message.highlightElements != null && message.highlightElements.length)
                        for (let i = 0; i < message.highlightElements.length; ++i)
                            writer.uint32(/* id 3, wireType 2 =*/26).string(message.highlightElements[i]);
                    if (message.$unknowns != null && $Object.hasOwnProperty.call(message, "$unknowns"))
                        for (let i = 0; i < message.$unknowns.length; ++i)
                            writer.raw(message.$unknowns[i]);
                    return writer;
                };

                /**
                 * Encodes the specified ScreenVisualCue message, length delimited. Does not implicitly {@link cerm.execution.v1.ScreenVisualCue.verify|verify} messages.
                 * @function encodeDelimited
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {cerm.execution.v1.ScreenVisualCue.$Properties} message ScreenVisualCue message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                ScreenVisualCue.encodeDelimited = function(message, writer) {
                    return this.encode(message, (writer || $Writer.create()).fork()).ldelim();
                };

                /**
                 * Decodes a ScreenVisualCue message from the specified reader or buffer.
                 * @function decode
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @param {number} [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape} ScreenVisualCue
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                ScreenVisualCue.decode = function (reader, length, _end, _depth, _target) {
                    if (!(reader instanceof $Reader))
                        reader = $Reader.create(reader);
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $Reader.recursionLimit)
                        throw $Error("max depth exceeded");
                    let end, message, value;
                    if (length === $undefined)
                        end = reader.len;
                    else {
                        end = reader.pos + length;
                        if (end > reader.len)
                            throw $RangeError("index out of range");
                        length = reader.len;
                        reader.len = end;
                    }
                    message = _target || new $root.cerm.execution.v1.ScreenVisualCue();
                    while (reader.pos < end) {
                        let start = reader.pos;
                        let tag = reader.tag();
                        if (tag === _end) {
                            _end = $undefined;
                            break;
                        }
                        let wireType = tag & 7;
                        switch (tag >>>= 3) {
                        case 1: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.animationId = value;
                                else
                                    delete message.animationId;
                                continue;
                            }
                        case 2: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.focusTargetId = value;
                                else
                                    delete message.focusTargetId;
                                continue;
                            }
                        case 3: {
                                if (wireType !== 2)
                                    break;
                                if (!(message.highlightElements && message.highlightElements.length))
                                    message.highlightElements = [];
                                message.highlightElements.push(reader.stringVerify());
                                continue;
                            }
                        }
                        reader.skipType(wireType, _depth, tag);
                        if (!reader.discardUnknown) {
                            $util.makeProp(message, "$unknowns", false);
                            (message.$unknowns || (message.$unknowns = [])).push(reader.raw(start, reader.pos));
                        }
                    }
                    if (length !== $undefined) {
                        if (reader.pos !== end)
                            throw $RangeError("index out of range");
                        reader.len = length;
                    }
                    if (_end !== $undefined)
                        throw $Error("missing end group");
                    return message;
                };

                /**
                 * Decodes a ScreenVisualCue message from the specified reader or buffer, length delimited.
                 * @function decodeDelimited
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape} ScreenVisualCue
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                ScreenVisualCue.decodeDelimited = function(reader) {
                    if (!(reader instanceof $Reader))
                        reader = new $Reader(reader);
                    return this.decode(reader, reader.size());
                };

                /**
                 * Verifies a ScreenVisualCue message.
                 * @function verify
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {Object.<string,*>} message Plain object to verify
                 * @returns {string|null} `null` if valid, otherwise the reason why it is not
                 */
                ScreenVisualCue.verify = function (message, _depth) {
                    if (typeof message !== "object" || message === null)
                        return "object expected";
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        return "max depth exceeded";
                    if (message.animationId != null && $Object.hasOwnProperty.call(message, "animationId"))
                        if (!$util.isString(message.animationId))
                            return "animationId: string expected";
                    if (message.focusTargetId != null && $Object.hasOwnProperty.call(message, "focusTargetId"))
                        if (!$util.isString(message.focusTargetId))
                            return "focusTargetId: string expected";
                    if (message.highlightElements != null && $Object.hasOwnProperty.call(message, "highlightElements")) {
                        if (!$Array.isArray(message.highlightElements))
                            return "highlightElements: array expected";
                        for (let i = 0; i < message.highlightElements.length; ++i)
                            if (!$util.isString(message.highlightElements[i]))
                                return "highlightElements: string[] expected";
                    }
                    return null;
                };

                /**
                 * Creates a ScreenVisualCue message from a plain object. Also converts values to their respective internal types.
                 * @function fromObject
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {Object.<string,*>} object Plain object
                 * @returns {cerm.execution.v1.ScreenVisualCue} ScreenVisualCue
                 */
                ScreenVisualCue.fromObject = function (object, _depth) {
                    if (object instanceof $root.cerm.execution.v1.ScreenVisualCue)
                        return object;
                    if (!$util.isObject(object))
                        throw $TypeError(".cerm.execution.v1.ScreenVisualCue: object expected");
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let message = new $root.cerm.execution.v1.ScreenVisualCue();
                    if (object.animationId != null)
                        if (typeof object.animationId !== "string" || object.animationId.length)
                            message.animationId = $String(object.animationId);
                    if (object.focusTargetId != null)
                        if (typeof object.focusTargetId !== "string" || object.focusTargetId.length)
                            message.focusTargetId = $String(object.focusTargetId);
                    if (object.highlightElements) {
                        if (!$Array.isArray(object.highlightElements))
                            throw $TypeError(".cerm.execution.v1.ScreenVisualCue.highlightElements: array expected");
                        message.highlightElements = $Array(object.highlightElements.length);
                        for (let i = 0; i < object.highlightElements.length; ++i)
                            message.highlightElements[i] = $String(object.highlightElements[i]);
                    }
                    return message;
                };

                /**
                 * Creates a plain object from a ScreenVisualCue message. Also converts values to other types if specified.
                 * @function toObject
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {cerm.execution.v1.ScreenVisualCue} message ScreenVisualCue
                 * @param {$protobuf.IConversionOptions} [options] Conversion options
                 * @returns {Object.<string,*>} Plain object
                 */
                ScreenVisualCue.toObject = function (message, options, _depth) {
                    if (!options)
                        options = {};
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let object = {};
                    if (options.arrays || options.defaults)
                        object.highlightElements = [];
                    if (options.defaults) {
                        object.animationId = "";
                        object.focusTargetId = "";
                    }
                    if (message.animationId != null && $Object.hasOwnProperty.call(message, "animationId"))
                        object.animationId = message.animationId;
                    if (message.focusTargetId != null && $Object.hasOwnProperty.call(message, "focusTargetId"))
                        object.focusTargetId = message.focusTargetId;
                    if (message.highlightElements && message.highlightElements.length) {
                        object.highlightElements = $Array(message.highlightElements.length);
                        for (let j = 0; j < message.highlightElements.length; ++j)
                            object.highlightElements[j] = message.highlightElements[j];
                    }
                    return object;
                };

                /**
                 * Converts this ScreenVisualCue to JSON.
                 * @function toJSON
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @instance
                 * @returns {Object.<string,*>} JSON object
                 */
                ScreenVisualCue.prototype.toJSON = function() {
                    return ScreenVisualCue.toObject(this, $protobuf.util.toJSONOptions);
                };

                /**
                 * Gets the type url for ScreenVisualCue
                 * @function getTypeUrl
                 * @memberof cerm.execution.v1.ScreenVisualCue
                 * @static
                 * @param {string} [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns {string} The type url
                 */
                ScreenVisualCue.getTypeUrl = function(prefix) {
                    if (prefix === $undefined)
                        prefix = "type.googleapis.com";
                    return prefix + "/cerm.execution.v1.ScreenVisualCue";
                };

                return ScreenVisualCue;
            })();

            v1.ElementSolution = (function() {

                /**
                 * Properties of an ElementSolution.
                 * @typedef {Object} cerm.execution.v1.ElementSolution.$Properties
                 * @property {string|null} [solutionId] ElementSolution solutionId
                 * @property {string|null} [actorId] ElementSolution actorId
                 * @property {cerm.execution.v1.EmotionType|null} [emotion] ElementSolution emotion
                 * @property {cerm.execution.v1.AudioPayload.$Properties|null} [speech] ElementSolution speech
                 * @property {Array.<cerm.execution.v1.KinematicGesture.$Properties>|null} [physicalGestures] ElementSolution physicalGestures
                 * @property {cerm.execution.v1.ScreenVisualCue.$Properties|null} [screenVisuals] ElementSolution screenVisuals
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */

                /**
                 * Properties of an ElementSolution.
                 * @memberof cerm.execution.v1
                 * @interface IElementSolution
                 * @augments cerm.execution.v1.ElementSolution.$Properties
                 * @deprecated Use cerm.execution.v1.ElementSolution.$Properties instead.
                 */

                /**
                 * Shape of an ElementSolution.
                 * @typedef {cerm.execution.v1.ElementSolution.$Properties} cerm.execution.v1.ElementSolution.$Shape
                 */

                /**
                 * Constructs a new ElementSolution.
                 * @memberof cerm.execution.v1
                 * @classdesc Represents an ElementSolution.
                 * @constructor
                 * @param {cerm.execution.v1.ElementSolution.$Properties=} [properties] Properties to set
                 * @property {Array.<Uint8Array>} [$unknowns] Unknown fields preserved while decoding when enabled
                 */
                const ElementSolution = function (properties) {
                    this.physicalGestures = [];
                    if (properties)
                        for (let keys = $Object.keys(properties), i = 0; i < keys.length; ++i)
                            if (properties[keys[i]] != null && keys[i] !== "__proto__")
                                this[keys[i]] = properties[keys[i]];
                };

                /**
                 * ElementSolution solutionId.
                 * @member {string} solutionId
                 * @memberof cerm.execution.v1.ElementSolution
                 * @instance
                 */
                ElementSolution.prototype.solutionId = "";

                /**
                 * ElementSolution actorId.
                 * @member {string} actorId
                 * @memberof cerm.execution.v1.ElementSolution
                 * @instance
                 */
                ElementSolution.prototype.actorId = "";

                /**
                 * ElementSolution emotion.
                 * @member {cerm.execution.v1.EmotionType} emotion
                 * @memberof cerm.execution.v1.ElementSolution
                 * @instance
                 */
                ElementSolution.prototype.emotion = 0;

                /**
                 * ElementSolution speech.
                 * @member {cerm.execution.v1.AudioPayload.$Properties|null|undefined} speech
                 * @memberof cerm.execution.v1.ElementSolution
                 * @instance
                 */
                ElementSolution.prototype.speech = null;

                /**
                 * ElementSolution physicalGestures.
                 * @member {Array.<cerm.execution.v1.KinematicGesture.$Properties>} physicalGestures
                 * @memberof cerm.execution.v1.ElementSolution
                 * @instance
                 */
                ElementSolution.prototype.physicalGestures = $util.emptyArray;

                /**
                 * ElementSolution screenVisuals.
                 * @member {cerm.execution.v1.ScreenVisualCue.$Properties|null|undefined} screenVisuals
                 * @memberof cerm.execution.v1.ElementSolution
                 * @instance
                 */
                ElementSolution.prototype.screenVisuals = null;

                /**
                 * Creates a new ElementSolution instance using the specified properties.
                 * @function create
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {cerm.execution.v1.ElementSolution.$Properties=} [properties] Properties to set
                 * @returns {cerm.execution.v1.ElementSolution} ElementSolution instance
                 * @type {{
                 *   (properties: cerm.execution.v1.ElementSolution.$Shape): cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape;
                 *   (properties?: cerm.execution.v1.ElementSolution.$Properties): cerm.execution.v1.ElementSolution;
                 * }}
                 */
                ElementSolution.create = function(properties) {
                    return new ElementSolution(properties);
                };

                /**
                 * Encodes the specified ElementSolution message. Does not implicitly {@link cerm.execution.v1.ElementSolution.verify|verify} messages.
                 * @function encode
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {cerm.execution.v1.ElementSolution.$Properties} message ElementSolution message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                ElementSolution.encode = function (message, writer, _depth) {
                    if (!writer)
                        writer = $Writer.create();
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    if (message.solutionId != null && $Object.hasOwnProperty.call(message, "solutionId") && message.solutionId !== "")
                        writer.uint32(/* id 1, wireType 2 =*/10).string(message.solutionId);
                    if (message.actorId != null && $Object.hasOwnProperty.call(message, "actorId") && message.actorId !== "")
                        writer.uint32(/* id 2, wireType 2 =*/18).string(message.actorId);
                    if (message.emotion != null && $Object.hasOwnProperty.call(message, "emotion") && message.emotion !== 0)
                        writer.uint32(/* id 3, wireType 0 =*/24).int32(message.emotion);
                    if (message.speech != null && $Object.hasOwnProperty.call(message, "speech"))
                        $root.cerm.execution.v1.AudioPayload.encode(message.speech, writer.uint32(/* id 4, wireType 2 =*/34).fork(), _depth + 1).ldelim();
                    if (message.physicalGestures != null && message.physicalGestures.length)
                        for (let i = 0; i < message.physicalGestures.length; ++i)
                            $root.cerm.execution.v1.KinematicGesture.encode(message.physicalGestures[i], writer.uint32(/* id 5, wireType 2 =*/42).fork(), _depth + 1).ldelim();
                    if (message.screenVisuals != null && $Object.hasOwnProperty.call(message, "screenVisuals"))
                        $root.cerm.execution.v1.ScreenVisualCue.encode(message.screenVisuals, writer.uint32(/* id 6, wireType 2 =*/50).fork(), _depth + 1).ldelim();
                    if (message.$unknowns != null && $Object.hasOwnProperty.call(message, "$unknowns"))
                        for (let i = 0; i < message.$unknowns.length; ++i)
                            writer.raw(message.$unknowns[i]);
                    return writer;
                };

                /**
                 * Encodes the specified ElementSolution message, length delimited. Does not implicitly {@link cerm.execution.v1.ElementSolution.verify|verify} messages.
                 * @function encodeDelimited
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {cerm.execution.v1.ElementSolution.$Properties} message ElementSolution message or plain object to encode
                 * @param {$protobuf.Writer} [writer] Writer to encode to
                 * @returns {$protobuf.Writer} Writer
                 */
                ElementSolution.encodeDelimited = function(message, writer) {
                    return this.encode(message, (writer || $Writer.create()).fork()).ldelim();
                };

                /**
                 * Decodes an ElementSolution message from the specified reader or buffer.
                 * @function decode
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @param {number} [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape} ElementSolution
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                ElementSolution.decode = function (reader, length, _end, _depth, _target) {
                    if (!(reader instanceof $Reader))
                        reader = $Reader.create(reader);
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $Reader.recursionLimit)
                        throw $Error("max depth exceeded");
                    let end, message, value;
                    if (length === $undefined)
                        end = reader.len;
                    else {
                        end = reader.pos + length;
                        if (end > reader.len)
                            throw $RangeError("index out of range");
                        length = reader.len;
                        reader.len = end;
                    }
                    message = _target || new $root.cerm.execution.v1.ElementSolution();
                    while (reader.pos < end) {
                        let start = reader.pos;
                        let tag = reader.tag();
                        if (tag === _end) {
                            _end = $undefined;
                            break;
                        }
                        let wireType = tag & 7;
                        switch (tag >>>= 3) {
                        case 1: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.solutionId = value;
                                else
                                    delete message.solutionId;
                                continue;
                            }
                        case 2: {
                                if (wireType !== 2)
                                    break;
                                if ((value = reader.stringVerify()).length)
                                    message.actorId = value;
                                else
                                    delete message.actorId;
                                continue;
                            }
                        case 3: {
                                if (wireType !== 0)
                                    break;
                                if (value = reader.int32())
                                    message.emotion = value;
                                else
                                    delete message.emotion;
                                continue;
                            }
                        case 4: {
                                if (wireType !== 2)
                                    break;
                                message.speech = $root.cerm.execution.v1.AudioPayload.decode(reader, reader.size(), $undefined, _depth + 1, message.speech);
                                continue;
                            }
                        case 5: {
                                if (wireType !== 2)
                                    break;
                                if (!(message.physicalGestures && message.physicalGestures.length))
                                    message.physicalGestures = [];
                                message.physicalGestures.push($root.cerm.execution.v1.KinematicGesture.decode(reader, reader.size(), $undefined, _depth + 1));
                                continue;
                            }
                        case 6: {
                                if (wireType !== 2)
                                    break;
                                message.screenVisuals = $root.cerm.execution.v1.ScreenVisualCue.decode(reader, reader.size(), $undefined, _depth + 1, message.screenVisuals);
                                continue;
                            }
                        }
                        reader.skipType(wireType, _depth, tag);
                        if (!reader.discardUnknown) {
                            $util.makeProp(message, "$unknowns", false);
                            (message.$unknowns || (message.$unknowns = [])).push(reader.raw(start, reader.pos));
                        }
                    }
                    if (length !== $undefined) {
                        if (reader.pos !== end)
                            throw $RangeError("index out of range");
                        reader.len = length;
                    }
                    if (_end !== $undefined)
                        throw $Error("missing end group");
                    return message;
                };

                /**
                 * Decodes an ElementSolution message from the specified reader or buffer, length delimited.
                 * @function decodeDelimited
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {$protobuf.Reader|Uint8Array} reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape} ElementSolution
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                ElementSolution.decodeDelimited = function(reader) {
                    if (!(reader instanceof $Reader))
                        reader = new $Reader(reader);
                    return this.decode(reader, reader.size());
                };

                /**
                 * Verifies an ElementSolution message.
                 * @function verify
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {Object.<string,*>} message Plain object to verify
                 * @returns {string|null} `null` if valid, otherwise the reason why it is not
                 */
                ElementSolution.verify = function (message, _depth) {
                    if (typeof message !== "object" || message === null)
                        return "object expected";
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        return "max depth exceeded";
                    if (message.solutionId != null && $Object.hasOwnProperty.call(message, "solutionId"))
                        if (!$util.isString(message.solutionId))
                            return "solutionId: string expected";
                    if (message.actorId != null && $Object.hasOwnProperty.call(message, "actorId"))
                        if (!$util.isString(message.actorId))
                            return "actorId: string expected";
                    if (message.emotion != null && $Object.hasOwnProperty.call(message, "emotion"))
                        if (typeof message.emotion !== "number" || (message.emotion | 0) !== message.emotion)
                            return "emotion: enum value expected";
                    if (message.speech != null && $Object.hasOwnProperty.call(message, "speech")) {
                        let error = $root.cerm.execution.v1.AudioPayload.verify(message.speech, _depth + 1);
                        if (error)
                            return "speech." + error;
                    }
                    if (message.physicalGestures != null && $Object.hasOwnProperty.call(message, "physicalGestures")) {
                        if (!$Array.isArray(message.physicalGestures))
                            return "physicalGestures: array expected";
                        for (let i = 0; i < message.physicalGestures.length; ++i) {
                            let error = $root.cerm.execution.v1.KinematicGesture.verify(message.physicalGestures[i], _depth + 1);
                            if (error)
                                return "physicalGestures." + error;
                        }
                    }
                    if (message.screenVisuals != null && $Object.hasOwnProperty.call(message, "screenVisuals")) {
                        let error = $root.cerm.execution.v1.ScreenVisualCue.verify(message.screenVisuals, _depth + 1);
                        if (error)
                            return "screenVisuals." + error;
                    }
                    return null;
                };

                /**
                 * Creates an ElementSolution message from a plain object. Also converts values to their respective internal types.
                 * @function fromObject
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {Object.<string,*>} object Plain object
                 * @returns {cerm.execution.v1.ElementSolution} ElementSolution
                 */
                ElementSolution.fromObject = function (object, _depth) {
                    if (object instanceof $root.cerm.execution.v1.ElementSolution)
                        return object;
                    if (!$util.isObject(object))
                        throw $TypeError(".cerm.execution.v1.ElementSolution: object expected");
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let message = new $root.cerm.execution.v1.ElementSolution();
                    if (object.solutionId != null)
                        if (typeof object.solutionId !== "string" || object.solutionId.length)
                            message.solutionId = $String(object.solutionId);
                    if (object.actorId != null)
                        if (typeof object.actorId !== "string" || object.actorId.length)
                            message.actorId = $String(object.actorId);
                    if (object.emotion !== 0 && (typeof object.emotion !== "string" || $root.cerm.execution.v1.EmotionType[object.emotion] !== 0))
                        switch (object.emotion) {
                        case "EMOTION_NEUTRAL":
                        case 0:
                            message.emotion = 0;
                            break;
                        case "EMOTION_CURIOSITY":
                        case 1:
                            message.emotion = 1;
                            break;
                        case "EMOTION_DISAPPOINTMENT":
                        case 2:
                            message.emotion = 2;
                            break;
                        case "EMOTION_AMUSEMENT":
                        case 3:
                            message.emotion = 3;
                            break;
                        case "EMOTION_ENCOURAGEMENT":
                        case 4:
                            message.emotion = 4;
                            break;
                        case "EMOTION_FRUSTRATION":
                        case 5:
                            message.emotion = 5;
                            break;
                        default:
                            if (typeof object.emotion === "number" && (object.emotion | 0) === object.emotion)
                                message.emotion = object.emotion;
                        }
                    if (object.speech != null) {
                        if (!$util.isObject(object.speech))
                            throw $TypeError(".cerm.execution.v1.ElementSolution.speech: object expected");
                        message.speech = $root.cerm.execution.v1.AudioPayload.fromObject(object.speech, _depth + 1);
                    }
                    if (object.physicalGestures) {
                        if (!$Array.isArray(object.physicalGestures))
                            throw $TypeError(".cerm.execution.v1.ElementSolution.physicalGestures: array expected");
                        message.physicalGestures = $Array(object.physicalGestures.length);
                        for (let i = 0; i < object.physicalGestures.length; ++i) {
                            if (!$util.isObject(object.physicalGestures[i]))
                                throw $TypeError(".cerm.execution.v1.ElementSolution.physicalGestures: object expected");
                            message.physicalGestures[i] = $root.cerm.execution.v1.KinematicGesture.fromObject(object.physicalGestures[i], _depth + 1);
                        }
                    }
                    if (object.screenVisuals != null) {
                        if (!$util.isObject(object.screenVisuals))
                            throw $TypeError(".cerm.execution.v1.ElementSolution.screenVisuals: object expected");
                        message.screenVisuals = $root.cerm.execution.v1.ScreenVisualCue.fromObject(object.screenVisuals, _depth + 1);
                    }
                    return message;
                };

                /**
                 * Creates a plain object from an ElementSolution message. Also converts values to other types if specified.
                 * @function toObject
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {cerm.execution.v1.ElementSolution} message ElementSolution
                 * @param {$protobuf.IConversionOptions} [options] Conversion options
                 * @returns {Object.<string,*>} Plain object
                 */
                ElementSolution.toObject = function (message, options, _depth) {
                    if (!options)
                        options = {};
                    if (_depth === $undefined)
                        _depth = 0;
                    if (_depth > $util.recursionLimit)
                        throw $Error("max depth exceeded");
                    let object = {};
                    if (options.arrays || options.defaults)
                        object.physicalGestures = [];
                    if (options.defaults) {
                        object.solutionId = "";
                        object.actorId = "";
                        object.emotion = options.enums === $String ? "EMOTION_NEUTRAL" : 0;
                        object.speech = null;
                        object.screenVisuals = null;
                    }
                    if (message.solutionId != null && $Object.hasOwnProperty.call(message, "solutionId"))
                        object.solutionId = message.solutionId;
                    if (message.actorId != null && $Object.hasOwnProperty.call(message, "actorId"))
                        object.actorId = message.actorId;
                    if (message.emotion != null && $Object.hasOwnProperty.call(message, "emotion"))
                        object.emotion = options.enums === $String ? $root.cerm.execution.v1.EmotionType[message.emotion] === $undefined ? message.emotion : $root.cerm.execution.v1.EmotionType[message.emotion] : message.emotion;
                    if (message.speech != null && $Object.hasOwnProperty.call(message, "speech"))
                        object.speech = $root.cerm.execution.v1.AudioPayload.toObject(message.speech, options, _depth + 1);
                    if (message.physicalGestures && message.physicalGestures.length) {
                        object.physicalGestures = $Array(message.physicalGestures.length);
                        for (let j = 0; j < message.physicalGestures.length; ++j)
                            object.physicalGestures[j] = $root.cerm.execution.v1.KinematicGesture.toObject(message.physicalGestures[j], options, _depth + 1);
                    }
                    if (message.screenVisuals != null && $Object.hasOwnProperty.call(message, "screenVisuals"))
                        object.screenVisuals = $root.cerm.execution.v1.ScreenVisualCue.toObject(message.screenVisuals, options, _depth + 1);
                    return object;
                };

                /**
                 * Converts this ElementSolution to JSON.
                 * @function toJSON
                 * @memberof cerm.execution.v1.ElementSolution
                 * @instance
                 * @returns {Object.<string,*>} JSON object
                 */
                ElementSolution.prototype.toJSON = function() {
                    return ElementSolution.toObject(this, $protobuf.util.toJSONOptions);
                };

                /**
                 * Gets the type url for ElementSolution
                 * @function getTypeUrl
                 * @memberof cerm.execution.v1.ElementSolution
                 * @static
                 * @param {string} [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns {string} The type url
                 */
                ElementSolution.getTypeUrl = function(prefix) {
                    if (prefix === $undefined)
                        prefix = "type.googleapis.com";
                    return prefix + "/cerm.execution.v1.ElementSolution";
                };

                return ElementSolution;
            })();

            return v1;
        })();

        return execution;
    })();

    return cerm;
})();

export {
  $root as default
};
