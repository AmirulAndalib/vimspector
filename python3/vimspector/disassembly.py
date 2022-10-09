# vimspector - A multi-language debugging system for Vim
# Copyright 2022 Ben Jackson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from vimspector import signs, utils

SIGN_ID = 1


class DisassemblyView( object ):
  def __init__( self, window, connection, api_prefix ):
    self._window = window
    self._api_prefix = api_prefix
    self._connection = connection

    self.current_frame = None
    self.current_instructions = None

    self._scratch_buffers = []
    self._signs = {
      'vimspectorPC': None,
    }

    with utils.LetCurrentWindow( self._window ):
      if utils.UseWinBar():
        pass

    signs.DefineProgramCounterSigns()


  def ConnectionUp( self, connection ):
    self._connection = connection


  def SetCurrentFrame( self, frame ):
    if not self._window.valid:
      return

    if not frame:
      # TODO(BenJ): Clear PC
      return

    if 'instructionPointerReference' not in frame:
      # TODO(BenJ): Clear PC
      return

    instructionPointerReference = frame[ 'instructionPointerReference' ]

    self.current_frame = frame;

    def handler( msg ):
      self.current_instructions = msg.get( 'body', {} ).get( 'instructions' ) 
      self._DrawInstructions()

    self._connection.DoRequest( handler, {
      'command': 'disassemble',
      'arguments': {
        'memoryReference': instructionPointerReference,
        'offset': 0,
        'instructionOffset': 0,
        'instructionCount': 60,
        'resolveSymbols': True
      }
    } )


  def Clear( self ):
    self._UndisplayPC()
    utils.ClearBuffer( self._window.buffer )


  def Reset( self ):
    self.Clear()

    for b in self._scratch_buffers:
      utils.CleanUpHiddenBuffer( b )

    self._scratch_buffers = []


  def _DrawInstructions( self ):
    if not self._window.valid:
      return

    if not self.current_instructions:
      return

    buf_name = os.path.join(
      '_vimspector_disassembly',
      self.current_frame[ 'instructionPointerReference' ] )
    buf = utils.BufferForFile( buf_name )
    self._scratch_buffers.append( buf )
    utils.SetUpHiddenBuffer( buf, buf_name )
    with utils.ModifiableScratchBuffer( buf ):
      utils.SetBufferContents( buf, [
        i[ 'instruction' ] for i in self.current_instructions
      ] )

    with utils.LetCurrentWindow( self._window ):
      utils.OpenFileInCurrentWindow( buf_name )

    self._DisplayPC( buf_name )


  def _DisplayPC( self, buf_name ):
    self._UndisplayPC()

    if 'line' not in self.current_frame or self.current_frame[ 'line' ] < 1:
      return

    if 'path' not in self.current_frame.get( 'source', {} ):
      return

    current_path = self.current_frame[ 'source' ][ 'path' ]
    current_line = self.current_frame[ 'line' ]

    # Try and map the current frame to instructions
    cur_location = None
    for instr_index, instruction in enumerate( self.current_instructions ):
      if cur_location is None:
        cur_location = instruction.get( 'location')

      if 'line' not in instruction:
        continue

      line = instruction[ 'line' ]
      location = instruction.get( 'location', cur_location )

      if not location or 'path' not in location:
        # TODO: what about sourceReference
        continue

      if location[ 'path' ] != current_path:
        continue

      if current_line < line:
        continue

      if 'endLine' in instruction and instruction[ 'endLine' ] < current_line:
        continue

      # Found it
      self._signs[ 'vimspectorPC' ] = SIGN_ID
      signs.PlaceSign( self._signs[ 'vimspectorPC' ],
                       'VimspectorDisassembly',
                       'vimspectorPC',
                       buf_name,
                       instr_index + 1 )

      break


  def _UndisplayPC( self ):
    if self._signs[ 'vimspectorPC' ]:
      signs.UnplaceSign( self._signs[ 'vimspectorPC' ],
                         'VimspectorDisassembly' )
      self._signs[ 'vimspectorPC' ] = None
