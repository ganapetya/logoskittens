import * as $protobuf from "protobufjs";

/** Namespace cerm. */
export namespace cerm {

    /** Namespace execution. */
    namespace execution {

        /** Namespace v1. */
        namespace v1 {

            /** EmotionType enum. */
            enum EmotionType {

                /** EMOTION_NEUTRAL value */
                EMOTION_NEUTRAL = 0,

                /** EMOTION_CURIOSITY value */
                EMOTION_CURIOSITY = 1,

                /** EMOTION_DISAPPOINTMENT value */
                EMOTION_DISAPPOINTMENT = 2,

                /** EMOTION_AMUSEMENT value */
                EMOTION_AMUSEMENT = 3,

                /** EMOTION_ENCOURAGEMENT value */
                EMOTION_ENCOURAGEMENT = 4,

                /** EMOTION_FRUSTRATION value */
                EMOTION_FRUSTRATION = 5
            }

            /**
             * Properties of a Vector3.
             * @deprecated Use cerm.execution.v1.Vector3.$Properties instead.
             */
            interface IVector3 extends cerm.execution.v1.Vector3.$Properties {
            }

            /** Represents a Vector3. */
            class Vector3 {

                /**
                 * Constructs a new Vector3.
                 * @param [properties] Properties to set
                 */
                constructor(properties?: cerm.execution.v1.Vector3.$Properties);

                /** Unknown fields preserved while decoding when enabled */
                $unknowns?: Uint8Array[];

                /** Vector3 x. */
                x: number;

                /** Vector3 y. */
                y: number;

                /** Vector3 z. */
                z: number;

                /**
                 * Creates a new Vector3 instance using the specified properties.
                 * @param [properties] Properties to set
                 * @returns Vector3 instance
                 */
                static create(properties: cerm.execution.v1.Vector3.$Shape): cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape;
                static create(properties?: cerm.execution.v1.Vector3.$Properties): cerm.execution.v1.Vector3;

                /**
                 * Encodes the specified Vector3 message. Does not implicitly {@link cerm.execution.v1.Vector3.verify|verify} messages.
                 * @param message Vector3 message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encode(message: cerm.execution.v1.Vector3.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Encodes the specified Vector3 message, length delimited. Does not implicitly {@link cerm.execution.v1.Vector3.verify|verify} messages.
                 * @param message Vector3 message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encodeDelimited(message: cerm.execution.v1.Vector3.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Decodes a Vector3 message from the specified reader or buffer.
                 * @param reader Reader or buffer to decode from
                 * @param [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape} Vector3
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decode(reader: ($protobuf.Reader|Uint8Array), length?: number): cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape;

                /**
                 * Decodes a Vector3 message from the specified reader or buffer, length delimited.
                 * @param reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape} Vector3
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decodeDelimited(reader: ($protobuf.Reader|Uint8Array)): cerm.execution.v1.Vector3 & cerm.execution.v1.Vector3.$Shape;

                /**
                 * Verifies a Vector3 message.
                 * @param message Plain object to verify
                 * @returns `null` if valid, otherwise the reason why it is not
                 */
                static verify(message: { [k: string]: any }): (string|null);

                /**
                 * Creates a Vector3 message from a plain object. Also converts values to their respective internal types.
                 * @param object Plain object
                 * @returns Vector3
                 */
                static fromObject(object: { [k: string]: any }): cerm.execution.v1.Vector3;

                /**
                 * Creates a plain object from a Vector3 message. Also converts values to other types if specified.
                 * @param message Vector3
                 * @param [options] Conversion options
                 * @returns Plain object
                 */
                static toObject(message: cerm.execution.v1.Vector3, options?: $protobuf.IConversionOptions): { [k: string]: any };

                /**
                 * Converts this Vector3 to JSON.
                 * @returns JSON object
                 */
                toJSON(): { [k: string]: any };

                /**
                 * Gets the type url for Vector3
                 * @param [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns The type url
                 */
                static getTypeUrl(prefix?: string): string;
            }

            namespace Vector3 {

                /** Properties of a Vector3. */
                interface $Properties {

                    /** Vector3 x */
                    x?: (number|null);

                    /** Vector3 y */
                    y?: (number|null);

                    /** Vector3 z */
                    z?: (number|null);

                    /** Unknown fields preserved while decoding when enabled */
                    $unknowns?: Uint8Array[];
                }

                /** Shape of a Vector3. */
                type $Shape = cerm.execution.v1.Vector3.$Properties;
            }

            /**
             * Properties of an AudioPayload.
             * @deprecated Use cerm.execution.v1.AudioPayload.$Properties instead.
             */
            interface IAudioPayload extends cerm.execution.v1.AudioPayload.$Properties {
            }

            /** Represents an AudioPayload. */
            class AudioPayload {

                /**
                 * Constructs a new AudioPayload.
                 * @param [properties] Properties to set
                 */
                constructor(properties?: cerm.execution.v1.AudioPayload.$Properties);

                /** Unknown fields preserved while decoding when enabled */
                $unknowns?: Uint8Array[];

                /** AudioPayload text. */
                text: string;

                /** AudioPayload languageCode. */
                languageCode: string;

                /** AudioPayload voiceModelId. */
                voiceModelId: string;

                /** AudioPayload precomputedAudioPcm. */
                precomputedAudioPcm: Uint8Array;

                /**
                 * Creates a new AudioPayload instance using the specified properties.
                 * @param [properties] Properties to set
                 * @returns AudioPayload instance
                 */
                static create(properties: cerm.execution.v1.AudioPayload.$Shape): cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape;
                static create(properties?: cerm.execution.v1.AudioPayload.$Properties): cerm.execution.v1.AudioPayload;

                /**
                 * Encodes the specified AudioPayload message. Does not implicitly {@link cerm.execution.v1.AudioPayload.verify|verify} messages.
                 * @param message AudioPayload message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encode(message: cerm.execution.v1.AudioPayload.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Encodes the specified AudioPayload message, length delimited. Does not implicitly {@link cerm.execution.v1.AudioPayload.verify|verify} messages.
                 * @param message AudioPayload message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encodeDelimited(message: cerm.execution.v1.AudioPayload.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Decodes an AudioPayload message from the specified reader or buffer.
                 * @param reader Reader or buffer to decode from
                 * @param [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape} AudioPayload
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decode(reader: ($protobuf.Reader|Uint8Array), length?: number): cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape;

                /**
                 * Decodes an AudioPayload message from the specified reader or buffer, length delimited.
                 * @param reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape} AudioPayload
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decodeDelimited(reader: ($protobuf.Reader|Uint8Array)): cerm.execution.v1.AudioPayload & cerm.execution.v1.AudioPayload.$Shape;

                /**
                 * Verifies an AudioPayload message.
                 * @param message Plain object to verify
                 * @returns `null` if valid, otherwise the reason why it is not
                 */
                static verify(message: { [k: string]: any }): (string|null);

                /**
                 * Creates an AudioPayload message from a plain object. Also converts values to their respective internal types.
                 * @param object Plain object
                 * @returns AudioPayload
                 */
                static fromObject(object: { [k: string]: any }): cerm.execution.v1.AudioPayload;

                /**
                 * Creates a plain object from an AudioPayload message. Also converts values to other types if specified.
                 * @param message AudioPayload
                 * @param [options] Conversion options
                 * @returns Plain object
                 */
                static toObject(message: cerm.execution.v1.AudioPayload, options?: $protobuf.IConversionOptions): { [k: string]: any };

                /**
                 * Converts this AudioPayload to JSON.
                 * @returns JSON object
                 */
                toJSON(): { [k: string]: any };

                /**
                 * Gets the type url for AudioPayload
                 * @param [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns The type url
                 */
                static getTypeUrl(prefix?: string): string;
            }

            namespace AudioPayload {

                /** Properties of an AudioPayload. */
                interface $Properties {

                    /** AudioPayload text */
                    text?: (string|null);

                    /** AudioPayload languageCode */
                    languageCode?: (string|null);

                    /** AudioPayload voiceModelId */
                    voiceModelId?: (string|null);

                    /** AudioPayload precomputedAudioPcm */
                    precomputedAudioPcm?: (Uint8Array|null);

                    /** Unknown fields preserved while decoding when enabled */
                    $unknowns?: Uint8Array[];
                }

                /** Shape of an AudioPayload. */
                type $Shape = cerm.execution.v1.AudioPayload.$Properties;
            }

            /**
             * Properties of a KinematicGesture.
             * @deprecated Use cerm.execution.v1.KinematicGesture.$Properties instead.
             */
            interface IKinematicGesture extends cerm.execution.v1.KinematicGesture.$Properties {
            }

            /** Represents a KinematicGesture. */
            class KinematicGesture {

                /**
                 * Constructs a new KinematicGesture.
                 * @param [properties] Properties to set
                 */
                constructor(properties?: cerm.execution.v1.KinematicGesture.$Properties);

                /** Unknown fields preserved while decoding when enabled */
                $unknowns?: Uint8Array[];

                /** KinematicGesture primitiveName. */
                primitiveName: string;

                /** KinematicGesture targetVector. */
                targetVector?: (cerm.execution.v1.Vector3.$Properties|null);

                /** KinematicGesture durationMs. */
                durationMs: number;

                /**
                 * Creates a new KinematicGesture instance using the specified properties.
                 * @param [properties] Properties to set
                 * @returns KinematicGesture instance
                 */
                static create(properties: cerm.execution.v1.KinematicGesture.$Shape): cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape;
                static create(properties?: cerm.execution.v1.KinematicGesture.$Properties): cerm.execution.v1.KinematicGesture;

                /**
                 * Encodes the specified KinematicGesture message. Does not implicitly {@link cerm.execution.v1.KinematicGesture.verify|verify} messages.
                 * @param message KinematicGesture message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encode(message: cerm.execution.v1.KinematicGesture.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Encodes the specified KinematicGesture message, length delimited. Does not implicitly {@link cerm.execution.v1.KinematicGesture.verify|verify} messages.
                 * @param message KinematicGesture message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encodeDelimited(message: cerm.execution.v1.KinematicGesture.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Decodes a KinematicGesture message from the specified reader or buffer.
                 * @param reader Reader or buffer to decode from
                 * @param [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape} KinematicGesture
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decode(reader: ($protobuf.Reader|Uint8Array), length?: number): cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape;

                /**
                 * Decodes a KinematicGesture message from the specified reader or buffer, length delimited.
                 * @param reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape} KinematicGesture
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decodeDelimited(reader: ($protobuf.Reader|Uint8Array)): cerm.execution.v1.KinematicGesture & cerm.execution.v1.KinematicGesture.$Shape;

                /**
                 * Verifies a KinematicGesture message.
                 * @param message Plain object to verify
                 * @returns `null` if valid, otherwise the reason why it is not
                 */
                static verify(message: { [k: string]: any }): (string|null);

                /**
                 * Creates a KinematicGesture message from a plain object. Also converts values to their respective internal types.
                 * @param object Plain object
                 * @returns KinematicGesture
                 */
                static fromObject(object: { [k: string]: any }): cerm.execution.v1.KinematicGesture;

                /**
                 * Creates a plain object from a KinematicGesture message. Also converts values to other types if specified.
                 * @param message KinematicGesture
                 * @param [options] Conversion options
                 * @returns Plain object
                 */
                static toObject(message: cerm.execution.v1.KinematicGesture, options?: $protobuf.IConversionOptions): { [k: string]: any };

                /**
                 * Converts this KinematicGesture to JSON.
                 * @returns JSON object
                 */
                toJSON(): { [k: string]: any };

                /**
                 * Gets the type url for KinematicGesture
                 * @param [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns The type url
                 */
                static getTypeUrl(prefix?: string): string;
            }

            namespace KinematicGesture {

                /** Properties of a KinematicGesture. */
                interface $Properties {

                    /** KinematicGesture primitiveName */
                    primitiveName?: (string|null);

                    /** KinematicGesture targetVector */
                    targetVector?: (cerm.execution.v1.Vector3.$Properties|null);

                    /** KinematicGesture durationMs */
                    durationMs?: (number|null);

                    /** Unknown fields preserved while decoding when enabled */
                    $unknowns?: Uint8Array[];
                }

                /** Shape of a KinematicGesture. */
                type $Shape = cerm.execution.v1.KinematicGesture.$Properties;
            }

            /**
             * Properties of a ScreenVisualCue.
             * @deprecated Use cerm.execution.v1.ScreenVisualCue.$Properties instead.
             */
            interface IScreenVisualCue extends cerm.execution.v1.ScreenVisualCue.$Properties {
            }

            /** Represents a ScreenVisualCue. */
            class ScreenVisualCue {

                /**
                 * Constructs a new ScreenVisualCue.
                 * @param [properties] Properties to set
                 */
                constructor(properties?: cerm.execution.v1.ScreenVisualCue.$Properties);

                /** Unknown fields preserved while decoding when enabled */
                $unknowns?: Uint8Array[];

                /** ScreenVisualCue animationId. */
                animationId: string;

                /** ScreenVisualCue focusTargetId. */
                focusTargetId: string;

                /** ScreenVisualCue highlightElements. */
                highlightElements: string[];

                /**
                 * Creates a new ScreenVisualCue instance using the specified properties.
                 * @param [properties] Properties to set
                 * @returns ScreenVisualCue instance
                 */
                static create(properties: cerm.execution.v1.ScreenVisualCue.$Shape): cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape;
                static create(properties?: cerm.execution.v1.ScreenVisualCue.$Properties): cerm.execution.v1.ScreenVisualCue;

                /**
                 * Encodes the specified ScreenVisualCue message. Does not implicitly {@link cerm.execution.v1.ScreenVisualCue.verify|verify} messages.
                 * @param message ScreenVisualCue message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encode(message: cerm.execution.v1.ScreenVisualCue.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Encodes the specified ScreenVisualCue message, length delimited. Does not implicitly {@link cerm.execution.v1.ScreenVisualCue.verify|verify} messages.
                 * @param message ScreenVisualCue message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encodeDelimited(message: cerm.execution.v1.ScreenVisualCue.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Decodes a ScreenVisualCue message from the specified reader or buffer.
                 * @param reader Reader or buffer to decode from
                 * @param [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape} ScreenVisualCue
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decode(reader: ($protobuf.Reader|Uint8Array), length?: number): cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape;

                /**
                 * Decodes a ScreenVisualCue message from the specified reader or buffer, length delimited.
                 * @param reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape} ScreenVisualCue
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decodeDelimited(reader: ($protobuf.Reader|Uint8Array)): cerm.execution.v1.ScreenVisualCue & cerm.execution.v1.ScreenVisualCue.$Shape;

                /**
                 * Verifies a ScreenVisualCue message.
                 * @param message Plain object to verify
                 * @returns `null` if valid, otherwise the reason why it is not
                 */
                static verify(message: { [k: string]: any }): (string|null);

                /**
                 * Creates a ScreenVisualCue message from a plain object. Also converts values to their respective internal types.
                 * @param object Plain object
                 * @returns ScreenVisualCue
                 */
                static fromObject(object: { [k: string]: any }): cerm.execution.v1.ScreenVisualCue;

                /**
                 * Creates a plain object from a ScreenVisualCue message. Also converts values to other types if specified.
                 * @param message ScreenVisualCue
                 * @param [options] Conversion options
                 * @returns Plain object
                 */
                static toObject(message: cerm.execution.v1.ScreenVisualCue, options?: $protobuf.IConversionOptions): { [k: string]: any };

                /**
                 * Converts this ScreenVisualCue to JSON.
                 * @returns JSON object
                 */
                toJSON(): { [k: string]: any };

                /**
                 * Gets the type url for ScreenVisualCue
                 * @param [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns The type url
                 */
                static getTypeUrl(prefix?: string): string;
            }

            namespace ScreenVisualCue {

                /** Properties of a ScreenVisualCue. */
                interface $Properties {

                    /** ScreenVisualCue animationId */
                    animationId?: (string|null);

                    /** ScreenVisualCue focusTargetId */
                    focusTargetId?: (string|null);

                    /** ScreenVisualCue highlightElements */
                    highlightElements?: (string[]|null);

                    /** Unknown fields preserved while decoding when enabled */
                    $unknowns?: Uint8Array[];
                }

                /** Shape of a ScreenVisualCue. */
                type $Shape = cerm.execution.v1.ScreenVisualCue.$Properties;
            }

            /**
             * Properties of an ElementSolution.
             * @deprecated Use cerm.execution.v1.ElementSolution.$Properties instead.
             */
            interface IElementSolution extends cerm.execution.v1.ElementSolution.$Properties {
            }

            /** Represents an ElementSolution. */
            class ElementSolution {

                /**
                 * Constructs a new ElementSolution.
                 * @param [properties] Properties to set
                 */
                constructor(properties?: cerm.execution.v1.ElementSolution.$Properties);

                /** Unknown fields preserved while decoding when enabled */
                $unknowns?: Uint8Array[];

                /** ElementSolution solutionId. */
                solutionId: string;

                /** ElementSolution actorId. */
                actorId: string;

                /** ElementSolution emotion. */
                emotion: cerm.execution.v1.EmotionType;

                /** ElementSolution speech. */
                speech?: (cerm.execution.v1.AudioPayload.$Properties|null);

                /** ElementSolution physicalGestures. */
                physicalGestures: cerm.execution.v1.KinematicGesture.$Properties[];

                /** ElementSolution screenVisuals. */
                screenVisuals?: (cerm.execution.v1.ScreenVisualCue.$Properties|null);

                /**
                 * Creates a new ElementSolution instance using the specified properties.
                 * @param [properties] Properties to set
                 * @returns ElementSolution instance
                 */
                static create(properties: cerm.execution.v1.ElementSolution.$Shape): cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape;
                static create(properties?: cerm.execution.v1.ElementSolution.$Properties): cerm.execution.v1.ElementSolution;

                /**
                 * Encodes the specified ElementSolution message. Does not implicitly {@link cerm.execution.v1.ElementSolution.verify|verify} messages.
                 * @param message ElementSolution message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encode(message: cerm.execution.v1.ElementSolution.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Encodes the specified ElementSolution message, length delimited. Does not implicitly {@link cerm.execution.v1.ElementSolution.verify|verify} messages.
                 * @param message ElementSolution message or plain object to encode
                 * @param [writer] Writer to encode to
                 * @returns Writer
                 */
                static encodeDelimited(message: cerm.execution.v1.ElementSolution.$Properties, writer?: $protobuf.Writer): $protobuf.Writer;

                /**
                 * Decodes an ElementSolution message from the specified reader or buffer.
                 * @param reader Reader or buffer to decode from
                 * @param [length] Message length if known beforehand
                 * @returns {cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape} ElementSolution
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decode(reader: ($protobuf.Reader|Uint8Array), length?: number): cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape;

                /**
                 * Decodes an ElementSolution message from the specified reader or buffer, length delimited.
                 * @param reader Reader or buffer to decode from
                 * @returns {cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape} ElementSolution
                 * @throws {Error} If the payload is not a reader or valid buffer
                 * @throws {$protobuf.util.ProtocolError} If required fields are missing
                 */
                static decodeDelimited(reader: ($protobuf.Reader|Uint8Array)): cerm.execution.v1.ElementSolution & cerm.execution.v1.ElementSolution.$Shape;

                /**
                 * Verifies an ElementSolution message.
                 * @param message Plain object to verify
                 * @returns `null` if valid, otherwise the reason why it is not
                 */
                static verify(message: { [k: string]: any }): (string|null);

                /**
                 * Creates an ElementSolution message from a plain object. Also converts values to their respective internal types.
                 * @param object Plain object
                 * @returns ElementSolution
                 */
                static fromObject(object: { [k: string]: any }): cerm.execution.v1.ElementSolution;

                /**
                 * Creates a plain object from an ElementSolution message. Also converts values to other types if specified.
                 * @param message ElementSolution
                 * @param [options] Conversion options
                 * @returns Plain object
                 */
                static toObject(message: cerm.execution.v1.ElementSolution, options?: $protobuf.IConversionOptions): { [k: string]: any };

                /**
                 * Converts this ElementSolution to JSON.
                 * @returns JSON object
                 */
                toJSON(): { [k: string]: any };

                /**
                 * Gets the type url for ElementSolution
                 * @param [prefix] Custom type url prefix, defaults to `"type.googleapis.com"`
                 * @returns The type url
                 */
                static getTypeUrl(prefix?: string): string;
            }

            namespace ElementSolution {

                /** Properties of an ElementSolution. */
                interface $Properties {

                    /** ElementSolution solutionId */
                    solutionId?: (string|null);

                    /** ElementSolution actorId */
                    actorId?: (string|null);

                    /** ElementSolution emotion */
                    emotion?: (cerm.execution.v1.EmotionType|null);

                    /** ElementSolution speech */
                    speech?: (cerm.execution.v1.AudioPayload.$Properties|null);

                    /** ElementSolution physicalGestures */
                    physicalGestures?: (cerm.execution.v1.KinematicGesture.$Properties[]|null);

                    /** ElementSolution screenVisuals */
                    screenVisuals?: (cerm.execution.v1.ScreenVisualCue.$Properties|null);

                    /** Unknown fields preserved while decoding when enabled */
                    $unknowns?: Uint8Array[];
                }

                /** Shape of an ElementSolution. */
                type $Shape = cerm.execution.v1.ElementSolution.$Properties;
            }
        }
    }
}
